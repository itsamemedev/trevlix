/**
 * TREVLIX – Central Socket Manager
 * =================================
 * Manages a single WebSocket connection with:
 * - Auto-reconnect with exponential backoff
 * - Duplicate connection prevention
 * - Event listener cleanup on reconnect
 * - Rate limiting for outgoing events
 * - Connection state tracking
 */

const TrevlixSocket = (function() {
  'use strict';

  let _socket = null;
  let _connected = false;
  let _handlers = {};        // event -> [handler] map
  let _emitTimestamps = {};  // rate limiting for outgoing events
  const MIN_EMIT_INTERVAL = 500; // ms between same events

  function _readTokenFromCookie() {
    const raw = (document.cookie.match(/(?:^|;\s*)token=([^;]*)/)||[])[1] || '';
    if (!raw) return '';
    try { return decodeURIComponent(raw); } catch(_e) { return raw; }
  }

  /**
   * Initialize the socket connection.
   * Safe to call multiple times - will reuse existing connection.
   * @param {Object} opts - Socket.io options override
   * @returns {SocketIO} The socket instance
   */
  function init(opts) {
    if (_socket && _socket.connected) return _socket;
    if (_socket) {
      // Cleanup stale socket
      off();
      try { _socket.disconnect(); } catch(e) {}
    }

    const jwtToken = _readTokenFromCookie();

    const defaultTransports = (window.TREVLIX_SOCKET_TRANSPORTS &&
      Array.isArray(window.TREVLIX_SOCKET_TRANSPORTS) &&
      window.TREVLIX_SOCKET_TRANSPORTS.length > 0)
      ? window.TREVLIX_SOCKET_TRANSPORTS
      : ['polling', 'websocket'];

    _socket = io(Object.assign({
      // Wichtig: polling zuerst verhindert Werkzeug-500s, wenn der Server
      // im threading-Mode läuft und native WebSockets nicht bereitstellt.
      transports: defaultTransports,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 2000,
      reconnectionDelayMax: 30000,
      randomizationFactor: 0.3,
      timeout: 20000,
      withCredentials: true,
      auth: jwtToken ? { token: jwtToken } : {},
    }, opts || {}));

    // Track connection state
    _socket.on('connect', () => { _connected = true; });
    _socket.on('disconnect', () => { _connected = false; });

    // Refresh token from cookie on reconnect attempt
    const _refreshAuthToken = () => {
      const freshToken = _readTokenFromCookie();
      if (freshToken) {
        _socket.auth = { token: freshToken };
      }
    };
    // socket.io-client sendet reconnect_attempt auf der Manager-Instanz,
    // nicht zuverlässig auf der Socket-Instanz.
    if (_socket.io && typeof _socket.io.on === 'function') {
      _socket.io.on('reconnect_attempt', _refreshAuthToken);
    }
    _socket.on('reconnect_attempt', _refreshAuthToken);

    return _socket;
  }

  /**
   * Register an event handler with automatic cleanup tracking.
   * @param {string} event - Event name
   * @param {Function} handler - Event handler
   */
  function on(event, handler) {
    if (!_socket) throw new Error('Socket not initialized. Call TrevlixSocket.init() first.');
    if (!_handlers[event]) _handlers[event] = [];
    if (_handlers[event].includes(handler)) return;
    _handlers[event].push(handler);
    _socket.on(event, handler);
  }

  /**
   * Remove all handlers for an event (or all events).
   * @param {string} [event] - Event name, or omit to remove all
   */
  function off(event) {
    if (!_socket) return;
    if (event) {
      (_handlers[event] || []).forEach(h => _socket.off(event, h));
      delete _handlers[event];
    } else {
      Object.keys(_handlers).forEach(ev => {
        _handlers[ev].forEach(h => _socket.off(ev, h));
      });
      _handlers = {};
    }
  }

  /**
   * Emit an event with optional rate limiting.
   * @param {string} event - Event name
   * @param {*} data - Event data
   * @param {boolean} [rateLimit=false] - Apply rate limiting
   */
  function emit(event, data, rateLimit) {
    if (!_socket) return;
    if (rateLimit) {
      const now = Date.now();
      if (_emitTimestamps[event] && (now - _emitTimestamps[event]) < MIN_EMIT_INTERVAL) {
        return; // Skip - too fast
      }
      _emitTimestamps[event] = now;
    }
    _socket.emit(event, data);
  }

  /**
   * Get connection state.
   * @returns {boolean}
   */
  function isConnected() { return _connected; }

  /**
   * Get the raw socket instance (for direct access when needed).
   * @returns {SocketIO|null}
   */
  function raw() { return _socket; }

  /**
   * Cleanup everything (call on page unload).
   */
  function destroy() {
    off();
    if (_socket) {
      try { _socket.disconnect(); } catch(e) {}
      _socket = null;
    }
    _connected = false;
    _handlers = {};
    _emitTimestamps = {};
  }

  return { init, on, off, emit, isConnected, raw, destroy };
})();

// Cleanup on page unload
window.addEventListener('beforeunload', () => TrevlixSocket.destroy());
