"""A minimal in-memory SMTP server for tests (no AUTH, no TLS): records what it receives."""
import socket
import threading


class SmtpSink:
    def __init__(self):
        self.messages = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._sock.close()

    def _serve(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        f = conn.makefile("rwb")

        def say(line):
            f.write(line.encode() + b"\r\n")
            f.flush()

        say("220 sink ESMTP")
        msg = {"from": None, "to": [], "data": b""}
        while True:
            line = f.readline()
            if not line:
                break
            cmd = line.decode(errors="replace").strip()
            up = cmd.upper()
            if up.startswith(("EHLO", "HELO")):
                say("250 sink")
            elif up.startswith("MAIL FROM"):
                msg["from"] = cmd[10:]
                say("250 ok")
            elif up.startswith("RCPT TO"):
                msg["to"].append(cmd[8:])
                say("250 ok")
            elif up == "DATA":
                say("354 go")
                data = b""
                while True:
                    chunk = f.readline()
                    if chunk in (b".\r\n", b".\n", b""):
                        break
                    data += chunk
                msg["data"] = data
                self.messages.append(msg)
                msg = {"from": None, "to": [], "data": b""}
                say("250 queued")
            elif up == "QUIT":
                say("221 bye")
                break
            else:
                say("250 ok")
        conn.close()
