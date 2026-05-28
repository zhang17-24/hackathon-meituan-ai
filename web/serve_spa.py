from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class SPAHandler(SimpleHTTPRequestHandler):
    def route_spa(self):
        requested = Path(self.translate_path(self.path))
        if not requested.exists() and "." not in Path(self.path).name:
            self.path = "/index.html"

    def do_GET(self):
        self.route_spa()
        return super().do_GET()

    def do_HEAD(self):
        self.route_spa()
        return super().do_HEAD()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8008), SPAHandler)
    print("Serving NailFlow at http://127.0.0.1:8008/")
    server.serve_forever()
