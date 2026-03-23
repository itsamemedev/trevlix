/**
 * TREVLIX – State Store
 * =====================
 * Simple, predictable state management for the dashboard.
 * Prevents double initialization and inconsistent state.
 *
 * Usage:
 *   TrevlixStore.set('botRunning', true);
 *   const val = TrevlixStore.get('botRunning');
 *   TrevlixStore.subscribe('botRunning', (newVal, oldVal) => { ... });
 */

const TrevlixStore = (function() {
  'use strict';

  const _state = {};
  const _subscribers = {};  // key -> [callback]
  let _initialized = false;

  /**
   * Initialize store with default values.
   * Safe to call multiple times - only first call has effect.
   * @param {Object} defaults - Default state values
   */
  function init(defaults) {
    if (_initialized) return;
    Object.assign(_state, defaults || {});
    _initialized = true;
  }

  /**
   * Get a state value.
   * @param {string} key
   * @param {*} [fallback] - Default if key not found
   * @returns {*}
   */
  function get(key, fallback) {
    return key in _state ? _state[key] : fallback;
  }

  /**
   * Set a state value and notify subscribers.
   * @param {string} key
   * @param {*} value
   */
  function set(key, value) {
    const old = _state[key];
    _state[key] = value;
    if (old !== value && _subscribers[key]) {
      _subscribers[key].forEach(cb => {
        try { cb(value, old); } catch(e) { console.error('Store subscriber error:', e); }
      });
    }
  }

  /**
   * Batch update multiple values (single notification pass).
   * @param {Object} updates - Key-value pairs to update
   */
  function update(updates) {
    if (!updates || typeof updates !== 'object') return;
    const changed = {};
    for (const [key, value] of Object.entries(updates)) {
      if (_state[key] !== value) {
        changed[key] = { old: _state[key], new: value };
        _state[key] = value;
      }
    }
    // Notify subscribers for changed keys
    for (const [key, diff] of Object.entries(changed)) {
      if (_subscribers[key]) {
        _subscribers[key].forEach(cb => {
          try { cb(diff.new, diff.old); } catch(e) { console.error('Store subscriber error:', e); }
        });
      }
    }
  }

  /**
   * Subscribe to changes for a specific key.
   * @param {string} key
   * @param {Function} callback - (newVal, oldVal) => void
   * @returns {Function} Unsubscribe function
   */
  function subscribe(key, callback) {
    if (!_subscribers[key]) _subscribers[key] = [];
    _subscribers[key].push(callback);
    return function unsubscribe() {
      _subscribers[key] = _subscribers[key].filter(cb => cb !== callback);
    };
  }

  /**
   * Get a snapshot of all state.
   * @returns {Object}
   */
  function snapshot() {
    return Object.assign({}, _state);
  }

  return { init, get, set, update, subscribe, snapshot };
})();
