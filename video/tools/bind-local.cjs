// Preload for Remotion Studio, which always binds every interface: force its server onto loopback.
const net = require('node:net')
const listen = net.Server.prototype.listen
net.Server.prototype.listen = function (...args) {
  if (args[0] && typeof args[0] === 'object' && 'port' in args[0]) args[0] = { ...args[0], host: '127.0.0.1' }
  return listen.apply(this, args)
}
