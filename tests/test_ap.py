from __future__ import annotations

from senseibox_wifi_ap_mode.ap import AccessPointSettings, render_dnsmasq_config, render_hostapd_config


def test_hostapd_config_is_generated_for_selected_interface():
    settings = AccessPointSettings(
        ssid="Senseibox Setup",
        passphrase="setup-password",
        gateway="setup-gateway",
        dhcp_start="setup-range-start",
        dhcp_end="setup-range-end",
    )

    config = render_hostapd_config("setup0", settings)

    assert "interface=setup0" in config
    assert "driver=nl80211" in config
    assert "ssid=Senseibox Setup" in config
    assert "country_code=GB" in config
    assert "hw_mode=g" in config
    assert "channel=6" in config
    assert "wpa=2" in config
    assert "wpa_passphrase=setup-password" in config
    assert "wpa_key_mgmt=WPA-PSK" in config
    assert "rsn_pairwise=CCMP" in config
    assert "bridge=" not in config


def test_dnsmasq_config_is_isolated_to_setup_interface():
    settings = AccessPointSettings(
        ssid="Senseibox Setup",
        passphrase="setup-password",
        gateway="setup-gateway",
        dhcp_start="setup-range-start",
        dhcp_end="setup-range-end",
    )

    config = render_dnsmasq_config("setup0", settings)

    assert "interface=setup0" in config
    assert "bind-interfaces" in config
    assert "port=0" in config
    assert "dhcp-leasefile=dnsmasq.leases" in config
    assert "dhcp-range=setup-range-start,setup-range-end,12h" in config


def test_ap_passphrase_rejects_newlines():
    settings = AccessPointSettings(
        ssid="Senseibox Setup",
        passphrase="bad\npassword",
        gateway="setup-gateway",
        dhcp_start="setup-range-start",
        dhcp_end="setup-range-end",
    )

    try:
        render_hostapd_config("setup0", settings)
    except ValueError as exc:
        assert "passphrase" in str(exc)
    else:
        raise AssertionError("Expected invalid passphrase to fail validation.")
