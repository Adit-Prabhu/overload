// Tells workers-types what the main module exports, so `exports.default` is typed in tests.
declare namespace Cloudflare {
  interface GlobalProps {
    mainModule: typeof import("./index");
  }
}
