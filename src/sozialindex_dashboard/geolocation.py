from __future__ import annotations

import streamlit as st

HTML = """
<div class="geolocation-control">
    <button id="locate" type="button">Standort ermitteln</button>
    <span id="status" aria-live="polite"></span>
</div>
"""

CSS = """
.geolocation-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 2.5rem;
  font-family: var(--st-font, sans-serif);
  font-size: var(--st-base-font-size, 1rem);
  color: var(--st-text-color, #31333f);
}

#locate {
  appearance: none;
  min-height: 2.5rem;
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--st-border-color, rgba(49, 51, 63, 0.2));
  border-radius: var(--st-button-radius, 0.5rem);
  background-color: var(--st-background-color, #ffffff);
  box-shadow: inset 0 0 0 1px transparent;
  color: var(--st-text-color, #31333f);
  font: inherit;
  font-weight: var(--st-base-font-weight, 400);
  line-height: 1.5;
  cursor: pointer;
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease,
    color 150ms ease;
}

#locate:hover {
  border-color: var(--st-primary-color, #ff4b4b);
  box-shadow: inset 0 0 0 1px var(--st-primary-color, #ff4b4b);
  color: var(--st-primary-color, #ff4b4b);
}

#locate:focus-visible {
  outline: 2px solid var(--st-primary-color, #ff4b4b);
  outline-offset: 2px;
}

#locate:active:not(:disabled) {
  color: var(--st-text-color, #31333f);
  border-color: var(--st-primary-color, #ff4b4b);
  box-shadow: inset 0 0 0 1px var(--st-primary-color, #ff4b4b);
}

#locate:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

#status {
  color: inherit;
  font-size: 0.875em;
}
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

    button.disabled = true
    status.textContent = "Standort wird angefragt..."
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setStateValue("latitude", position.coords.latitude)
        setStateValue("longitude", position.coords.longitude)
        setStateValue("accuracy", position.coords.accuracy)
        setStateValue("error", null)
        status.textContent = "Standort übernommen"
        button.disabled = false
      },
      (error) => {
        setStateValue("error", error.message)
        status.textContent = "Standortfreigabe nicht möglich"
        button.disabled = false
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    )
  }
}
"""

_GEOLOCATION_COMPONENT = st.components.v2.component(
    "browser_geolocation",
    html=HTML,
    css=CSS,
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
