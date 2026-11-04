"""The mailer service: consumes the 'mail' queue and sends through SMTP."""
import logging

from .. import config
from .. import log as flog
from ..queue import Runner
from . import smtp

log = logging.getLogger("farglow.mailer")


def send_job(job: dict, settings: config.Settings) -> None:
    p = job["payload"]
    try:
        mid = smtp.send(settings, p["to"], p["subject"], p["text"], p.get("html"))
    except smtp.MailDisabled:
        # Mail is optional for a LAN server: record and drop instead of retrying forever.
        log.warning("mail disabled; message dropped", extra={"subject": p.get("subject")})
        return
    log.info("mail sent", extra={"message_id": mid})


def main() -> int:
    settings = config.load("mailer")
    flog.setup("mailer", settings.log_level)
    if not settings.mail_enabled:
        log.warning("SMTP_HOST is empty: mail is disabled, queued mail will be dropped")
    Runner(settings, "mailer", ["mail"], {"mail.send": send_job}).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
