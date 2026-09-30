// OB's production wrapper revokes a blob URL immediately after constructing
// the worker, before WebKit has loaded it. Our prebuilt workers are served from
// the same origin, so they can be loaded directly without a temporary blob URL.
export class CorsWorker {
  private worker: Worker;

  /** Start a same-origin prebuilt SQL worker directly, avoiding the upstream blob-URL revocation race. */
  constructor(url: string | URL) {
    this.worker = new Worker(url);
  }

  /** Expose the underlying worker through the interface expected by the OB plugin. */
  getWorker() {
    return this.worker;
  }
}
