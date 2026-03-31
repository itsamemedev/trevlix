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
      try { _socket.disconnect(); } catch(e) {}
    }

    const jwtToken = (document.cookie.match(/(?:^|;\s*)token=([^;]*)/)||[])[1] || '';

    _socket = io(Object.assign({
      transports: ['websocket', 'polling'],
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
    _socket.on('reconnect_attempt', () => {
      const freshToken = (document.cookie.match(/(?:^|;\s*)token=([^;]*)/)||[])[1] || '';
      if (freshToken) {
        _socket.auth = { token: freshToken };
      }
    });

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
