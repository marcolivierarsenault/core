"""Support for Ecobee binary sensors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

ATTR_VENTILATOR_MIN_ON_TIME_HOME = "ventilator_min_on_time_home"
ATTR_VENTILATOR_MIN_ON_TIME_AWAY = "ventilator_min_on_time_away"
ATTR_IS_VENTILATOR_TIMER_ON = "is_ventilator_timer_on"

SERVICE_SET_VENTILATOR_MIN_ON_TIME_HOME = "set_ventilator_min_on_time_home"
SERVICE_SET_VENTILATOR_MIN_ON_TIME_AWAY = "set_ventilator_min_on_time_away"
SERVICE_SET_VENTILATOR_TIMER = "set_ventilator_timer"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up ecobee binary (occupancy) sensors."""
    data = hass.data[DOMAIN]
    dev = []
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue

                dev.append(EcobeeBinarySensor(data, sensor["name"], index))

        # ventilator
        entities = []
        thermostat = data.ecobee.get_thermostat(index)
        if thermostat["settings"]["ventilatorType"] != "none":
            entities.append(EcobeeVentilator(data, thermostat["name"], index))

    async_add_entities(dev, True)
    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_VENTILATOR_MIN_ON_TIME_HOME,
        {
            vol.Required(ATTR_VENTILATOR_MIN_ON_TIME_HOME): vol.Coerce(int),
        },
        "set_ventilator_min_on_time_home",
    )

    platform.async_register_entity_service(
        SERVICE_SET_VENTILATOR_MIN_ON_TIME_AWAY,
        {
            vol.Required(ATTR_VENTILATOR_MIN_ON_TIME_AWAY): vol.Coerce(int),
        },
        "set_ventilator_min_on_time_away",
    )

    platform.async_register_entity_service(
        SERVICE_SET_VENTILATOR_TIMER,
        {
            vol.Required(ATTR_IS_VENTILATOR_TIMER_ON): cv.boolean,
        },
        "set_ventilator_timer",
    )


class EcobeeVentilator(BinarySensorEntity):
    """Representation of an ventilator."""

    def __init__(self, data, name, thermostat_index):
        """Initialize the Ecobee ventilator."""
        self.data = data
        self._name = f"{name} Ventilator"
        self.sensor_name = f"{name} Ventilator"
        self.thermostat = self.data.ecobee.get_thermostat(thermostat_index)
        self.thermostat_index = thermostat_index
        self._state = "ventilator" in self.thermostat["equipmentStatus"]

    @property
    def name(self):
        """Return the name of the Ecobee Ventilator."""
        return self._name.rstrip()

    @property
    def unique_id(self):
        """Return a unique identifier for this ventilator."""
        return f"{self.thermostat['identifier']}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for the ecobee ventilator."""
        model: str | None
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[self.thermostat['modelNumber']]} Thermostat"
        except KeyError:
            # Ecobee model is not in our list
            model = None

        return DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=model,
            name=self.name,
        )

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        return thermostat["runtime"]["connected"]

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return "ventilator" in self.thermostat["equipmentStatus"]

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return BinarySensorDeviceClass.RUNNING

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "vent": self.thermostat["settings"]["vent"],
            "ventilator_min_on_time_home": self.thermostat["settings"][
                "ventilatorMinOnTimeHome"
            ],
            "ventilator_min_on_time_away": self.thermostat["settings"][
                "ventilatorMinOnTimeAway"
            ],
            "is_ventilator_timer_on": self.thermostat["settings"][
                "isVentilatorTimerOn"
            ],
        }

    def set_ventilator_min_on_time_home(self, ventilator_min_on_time_home):
        """Set the minimum ventilator on time for home mode."""
        self.data.ecobee.set_ventilator_min_on_time_home(
            self.thermostat_index, ventilator_min_on_time_home
        )

    def set_ventilator_min_on_time_away(self, ventilator_min_on_time_away):
        """Set the minimum ventilator on time for away mode."""
        self.data.ecobee.set_ventilator_min_on_time_away(
            self.thermostat_index, ventilator_min_on_time_away
        )

    def set_ventilator_timer(self, is_ventilator_timer_on):
        """Set the ventilator timer.

        If set to true, the ventilator_off_date_time is set to now() + 20 minutes,
        ventilator will start running and stop after 20 minutes.
        If set to false, the ventilator_off_date_time is set to it's default value,
        ventilator will stop.
        """
        self.data.ecobee.set_ventilator_timer(
            self.thermostat_index, is_ventilator_timer_on
        )


class EcobeeBinarySensor(BinarySensorEntity):
    """Representation of an Ecobee sensor."""

    def __init__(self, data, sensor_name, sensor_index):
        """Initialize the Ecobee sensor."""
        self.data = data
        self._name = f"{sensor_name} Occupancy"
        self.sensor_name = sensor_name
        self.index = sensor_index
        self._state = None

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name.rstrip()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                if "code" in sensor:
                    return f"{sensor['code']}-{self.device_class}"
                thermostat = self.data.ecobee.get_thermostat(self.index)
                return f"{thermostat['identifier']}-{sensor['id']}-{self.device_class}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""
        identifier = None
        model = None
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            if "code" in sensor:
                identifier = sensor["code"]
                model = "ecobee Room Sensor"
            else:
                thermostat = self.data.ecobee.get_thermostat(self.index)
                identifier = thermostat["identifier"]
                try:
                    model = (
                        f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
                    )
                except KeyError:
                    # Ecobee model is not in our list
                    model = None
            break

        if identifier is not None:
            return DeviceInfo(
                identifiers={(DOMAIN, identifier)},
                manufacturer=MANUFACTURER,
                model=model,
                name=self.sensor_name,
            )
        return None

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        thermostat = self.data.ecobee.get_thermostat(self.index)
        return thermostat["runtime"]["connected"]

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == "true"

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return BinarySensorDeviceClass.OCCUPANCY

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue
                self._state = item["value"]
                break
