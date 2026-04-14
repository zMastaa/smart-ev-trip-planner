"""Config flow for Smart Trip Planner."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_BUFFER_PERCENT,
    CONF_CALENDAR_ENTITY,
    CONF_GOOGLE_MAPS_API_KEY,
    CONF_RANGE_ENTITY,
    CONF_ROUTING_MODE,
    DEFAULT_BUFFER_PERCENT,
    DEFAULT_NAME,
    DEFAULT_ROUTING_MODE,
    DOMAIN,
    GOOGLE_DISTANCE_MATRIX_URL,
    ROUTING_MODE_ROUND_TRIP,
    ROUTING_MODE_SEQUENTIAL,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict | None = None) -> vol.Schema:
    """Build the config schema, optionally pre-filling with existing values."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CALENDAR_ENTITY,
                default=d.get(CONF_CALENDAR_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar")
            ),
            vol.Required(
                CONF_BATTERY_ENTITY,
                default=d.get(CONF_BATTERY_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_RANGE_ENTITY,
                default=d.get(CONF_RANGE_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_BUFFER_PERCENT,
                default=d.get(CONF_BUFFER_PERCENT, DEFAULT_BUFFER_PERCENT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=50,
                    step=5,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_ROUTING_MODE,
                default=d.get(CONF_ROUTING_MODE, DEFAULT_ROUTING_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=ROUTING_MODE_SEQUENTIAL,
                            label="Sequential — Home → E1 → E2 → Home",
                        ),
                        selector.SelectOptionDict(
                            value=ROUTING_MODE_ROUND_TRIP,
                            label="Round trip per event — Home → E1 → Home, Home → E2 → Home",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_GOOGLE_MAPS_API_KEY,
                default=d.get(CONF_GOOGLE_MAPS_API_KEY, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


async def _test_google_maps_key(api_key: str) -> str | None:
    """
    Make a minimal Distance Matrix request to verify the API key is valid
    and the Distance Matrix API is enabled on the project.
    Returns None on success, or an error key string on failure.
    """
    params = {
        "origins": "51.5074,-0.1278",   # London
        "destinations": "48.8566,2.3522",  # Paris
        "mode": "driving",
        "key": api_key,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(GOOGLE_DISTANCE_MATRIX_URL, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except aiohttp.ClientError:
        return "cannot_connect"

    status = data.get("status", "")
    if status == "OK":
        return None
    if status in ("REQUEST_DENIED", "INVALID_REQUEST"):
        return "invalid_api_key"
    return "cannot_connect"


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate that the selected entities exist and the API key works."""
    for key in (CONF_BATTERY_ENTITY, CONF_RANGE_ENTITY):
        state = hass.states.get(data[key])
        if state is None:
            raise ValueError("invalid_sensor")

    cal_state = hass.states.get(data[CONF_CALENDAR_ENTITY])
    if cal_state is None:
        raise ValueError("cannot_connect")

    error = await _test_google_maps_key(data[CONF_GOOGLE_MAPS_API_KEY])
    if error:
        raise ValueError(error)


class SmartTripPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Trip Planner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._async_abort_entries_match()

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_input(self.hass, user_input)
            except ValueError as exc:
                errors["base"] = str(exc)
            except Exception:
                _LOGGER.exception("Unexpected exception during config validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )
