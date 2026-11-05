/** Transport adaptation only; the upstream App and all its UI stay intact. */
const prefix = '/paper-research-coach';
function route(value: string | URL) {
  const url = new URL(String(value), location.href);
  if (url.origin === location.origin && (url.pathname.startsWith('/api/') || url.pathname === '/' || url.pathname === '/index.html')) {
    url.pathname = prefix + url.pathname;
  }
  return url.href;
}
const originalFetch = window.fetch.bind(window);
window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
  if (input instanceof Request) return originalFetch(new Request(route(input.url), input), init);
  return originalFetch(route(input), init);
};
// PDF.js uses XHR for non-HTTP application schemes, even when fetch is
// available. Route that carrier through the same authenticated mount as well.
const originalXhrOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(this: XMLHttpRequest, method: string, url: string | URL, asyncRequest: boolean = true, username?: string | null, password?: string | null) {
  return originalXhrOpen.call(this, method, route(url), asyncRequest, username, password);
};
const originalOpen = window.open.bind(window);
window.open = ((url?: string | URL, target?: string, features?: string) => originalOpen(url ? route(url) : url, target, features)) as typeof window.open;

// Electron's custom application scheme supports fetch streams. This small SSE
// carrier also preserves reconnect and cancellation on that scheme.
class HarnessEventSource extends EventTarget {
  static CONNECTING = 0; static OPEN = 1; static CLOSED = 2;
  CONNECTING = 0; OPEN = 1; CLOSED = 2;
  readyState = 0; withCredentials: boolean; url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  private controller?: AbortController;
  private timer?: number;
  private lastId = '';
  private retry = 1500;
  constructor(url: string | URL, options?: EventSourceInit) {
    super(); this.url = route(url); this.withCredentials = !!options?.withCredentials; void this.connect();
  }
  close() {this.readyState = 2; this.controller?.abort(); if (this.timer) clearTimeout(this.timer);}
  private emit(event: Event) {
    this.dispatchEvent(event);
    if (event.type === 'open') this.onopen?.(event);
    if (event.type === 'error') this.onerror?.(event);
    if (event.type === 'message') this.onmessage?.(event as MessageEvent);
  }
  private async connect() {
    this.controller = new AbortController();
    try {
      const response = await originalFetch(this.url, {signal: this.controller.signal, credentials: 'same-origin', headers: {Accept: 'text/event-stream', ...(this.lastId ? {'Last-Event-ID': this.lastId} : {})}});
      if (!response.ok || !response.body) throw new Error('Event stream unavailable');
      if (this.readyState === 2) return;
      this.readyState = 1; this.emit(new Event('open'));
      const reader = response.body.getReader(), decoder = new TextDecoder();
      let pending = '', data: string[] = [], eventType = 'message';
      const line = (value: string) => {
        if (!value) {
          if (data.length) this.emit(new MessageEvent(eventType || 'message', {data: data.join('\n'), lastEventId: this.lastId, origin: location.origin}));
          data = []; eventType = 'message'; return;
        }
        if (value.startsWith(':')) return;
        const colon = value.indexOf(':'), key = colon < 0 ? value : value.slice(0, colon);
        const raw = colon < 0 ? '' : value.slice(colon + 1), content = raw.startsWith(' ') ? raw.slice(1) : raw;
        if (key === 'data') data.push(content);
        if (key === 'event') eventType = content;
        if (key === 'id' && !content.includes('\0')) this.lastId = content;
        if (key === 'retry' && /^\d+$/.test(content)) this.retry = Number(content);
      };
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        pending += decoder.decode(chunk.value, {stream: true});
        let end: number;
        while ((end = pending.indexOf('\n')) >= 0) {line(pending.slice(0, end).replace(/\r$/, '')); pending = pending.slice(end + 1);}
      }
    } catch { /* Reconnect below, except after deliberate close. */ }
    if (this.readyState !== 2) {this.readyState = 0; this.emit(new Event('error')); this.timer = window.setTimeout(() => void this.connect(), this.retry);}
  }
}
window.EventSource = HarnessEventSource as unknown as typeof EventSource;

// Same-origin document isolation retains upstream CSS, dialogs and PDF layout.
new MutationObserver(() => {
  document.querySelectorAll<HTMLAnchorElement>('a[href^="/api/"]').forEach(a => a.setAttribute('href', prefix + a.getAttribute('href')));
}).observe(document.documentElement, {childList: true, subtree: true});
