"""极简静态服务：只认 /<token>/、/<token>/plan.md、/<token>/map.jpg，其余一律 404（不列目录）。
文件放在 /srv/trip-pages/<token>/；有 index.html.gz 且客户端接受 gzip 时直接回压缩版。"""
import http.server, os, re

ROOT, PORT = '/srv/trip-pages', int(os.environ.get('PORT', '28765'))
NAMES = {'': ('index.html', 'text/html; charset=utf-8'), 'index.html': ('index.html', 'text/html; charset=utf-8'),
         'plan.md': ('plan.md', 'text/plain; charset=utf-8'), 'map.jpg': ('map.jpg', 'image/jpeg')}


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, body):
        m = re.fullmatch(r'/([a-z0-9-]{8,64})/?([a-z.]*)', self.path.split('?')[0])
        if not m or m.group(2) not in NAMES:
            return self.send_error(404)
        name, ctype = NAMES[m.group(2)]
        f = os.path.join(ROOT, m.group(1), name)
        if not os.path.isfile(f):
            return self.send_error(404)
        gz = os.path.isfile(f + '.gz') and 'gzip' in self.headers.get('Accept-Encoding', '')
        data = open(f + '.gz' if gz else f, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        if gz:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Robots-Tag', 'noindex')
        self.end_headers()
        if body:
            self.wfile.write(data)

    def do_GET(self):
        self._send(True)

    def do_HEAD(self):
        self._send(False)

    def log_message(self, *a):
        pass


http.server.ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
