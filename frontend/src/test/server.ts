import { setupServer } from "msw/node";

/** MSW server for component tests. Each test adds the API answers it needs with `server.use`. */
export const server = setupServer();
