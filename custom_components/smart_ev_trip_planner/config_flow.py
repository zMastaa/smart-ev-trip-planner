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
    DEFAULT_BUFFER_PERCENT,
    DEFAULT_NAME,
    DOMAIN,
    GOOGLE_ROUTES_MATRIX_URL,
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
    Make a minimal Routes API request to verify the API key is valid
    and the Routes API is enabled on the project.
    Returns None on success, or an error key string on failure.
    """
    body = {
        "origins": [{"waypoint": {"location": {"latLng": {"latitude": 51.5074, "longitude": -0.1278}}}}],
        "destinations": [{"waypoint": {"location": {"latLng": {"latitude": 48.8566, "longitude": 2.3522}}}}],
        "travelMode": "DRIVE",
    }
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,condition",
        "Content-Type": "application/json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GOOGLE_ROUTES_MATRIX_URL, json=body, headers=headers) as resp:
                if resp.status in (401, 403):
                    return "invalid_api_key"
                resp.raise_for_status()
    except aiohttp.ClientResponseError:
        return "invalid_api_key"
    except aiohttp.ClientError:
        return "cannot_connect"

    return None


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
