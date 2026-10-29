// Expose a loopback port on the Tailscale address only: node tools/tailnet-forward.cjs <tailnet-ip> <port> <local-port>
const net = require('node:net')
const [host, port, local] = process.argv.slice(2)
net.createServer((c) => { const u = net.connect(Number(local), '127.0.0.1'); c.pipe(u).pipe(c); u.on('error', () => c.destroy()); c.on('error', () => u.destroy()) })
  .listen(Number(port), host, () => console.log(`forwarding ${host}:${port} → 127.0.0.1:${local}`))
