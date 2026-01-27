# Vanderbilt SPC (Web UI)

This integration connects Home Assistant to a Vanderbilt SPC alarm panel using its built-in Web UI.

It provides:

- An `alarm_control_panel` entity for **All Areas**
- Live state updates (armed away / disarmed)
- Arm / disarm control from Home Assistant
- Configurable polling interval

No external bridge is required.

---

## ⚠️ Important security note

SPC panels use a **very old TLS implementation**:

- TLS 1.2 only
- Self-signed certificates
- Legacy RSA cipher (`AES256-SHA`)
- Unsafe renegotiation

To support this, the integration deliberately relaxes OpenSSL security settings.

**Do not expose your SPC panel to the public internet.**  
Use this integration only on trusted local networks or via VPN.

---

## Installation

### Manual (custom integration)

1. Copy the `custom_components/spc_webui` folder in `config/custom_components` in Home Assistant.
2. Restart Home Assistant.

---

## Limitations

- Only **All Areas** is supported
- Only `Unset` and `Fullset` are implemented
- No event push – polling only
- Depends on the Web UI remaining compatible

---

## Disclaimer

This integration is not affiliated with Vanderbilt.

Use at your own risk. Alarm systems are security-critical infrastructure.

---

## License

MIT
