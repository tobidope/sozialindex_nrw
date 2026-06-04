from __future__ import annotations

import streamlit as st

HTML = """
<button id="locate" type="button">Standort ermitteln</button>
<span id="status"></span>
"""

JS = """
export default function (component) {
  const { parentElement, setStateValue } = component
  const button = parentElement.querySelector("#locate")
  const status = parentElement.querySelector("#status")
  if (!button || !status) return

  button.onclick = () => {
    if (!navigator.geolocation) {
      status.textContent = " Standort nicht verfügbar"
      setStateValue("error", "geolocation_unavailable")
      return
    }

    status.textContent = " Standort wird angefragt..."
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setStateValue("latitude", position.coords.latitude)
        setStateValue("longitude", position.coords.longitude)
        setStateValue("accuracy", position.coords.accuracy)
        setStateValue("error", null)
        status.textContent = " Standort übernommen"
      },
      (error) => {
        setStateValue("error", error.message)
        status.textContent = " Standortfreigabe nicht möglich"
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    )
  }
}
"""

_GEOLOCATION_COMPONENT = st.components.v2.component(
    "browser_geolocation",
    html=HTML,
    js=JS,
)


def browser_geolocation(key: str = "browser-geolocation"):
    return _GEOLOCATION_COMPONENT(
        key=key,
        on_latitude_change=lambda: None,
        on_longitude_change=lambda: None,
        on_accuracy_change=lambda: None,
        on_error_change=lambda: None,
    )
