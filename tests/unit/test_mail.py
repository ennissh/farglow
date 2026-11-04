import pytest
from conftest import make_settings
from smtp_sink import SmtpSink

from farglow.mail import smtp


def test_send_through_sink():
    with SmtpSink() as sink:
        s = make_settings(smtp_host="127.0.0.1", smtp_port=sink.port, smtp_security="none",
                          mail_from="Farglow <dispatch@example.test>", domain="example.test")
        smtp.send(s, "player@example.test", "Morning Dispatch", "Quiet night.")
    assert len(sink.messages) == 1
    assert b"Subject: Morning Dispatch" in sink.messages[0]["data"]


def test_disabled_without_host():
    with pytest.raises(smtp.MailDisabled):
        smtp.send(make_settings(smtp_host=""), "a@b.c", "s", "t")
