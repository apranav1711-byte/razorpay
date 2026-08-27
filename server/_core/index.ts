import "dotenv/config";
import { spawn } from "child_process";
import { createHash } from "crypto";
import express from "express";
import { createServer } from "http";
import net from "net";
import { createExpressMiddleware } from "@trpc/server/adapters/express";
import { registerOAuthRoutes } from "./oauth";
import { registerStorageProxy } from "./storageProxy";
import { appRouter } from "../routers";
import { createContext } from "./context";
import { sdk } from "./sdk";
import { serveStatic, setupVite } from "./vite";

function isPortAvailable(port: number): Promise<boolean> {
  return new Promise(resolve => {
    const server = net.createServer();
    server.listen(port, () => {
      server.close(() => resolve(true));
    });
    server.on("error", () => resolve(false));
  });
}

async function findAvailablePort(startPort: number = 3000): Promise<number> {
  for (let port = startPort; port < startPort + 20; port++) {
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  throw new Error(`No available port found starting from ${startPort}`);
}

async function startServer() {
  const importGatewayToken = process.env.JWT_SECRET
    ? createHash("sha256").update(`${process.env.JWT_SECRET}:chargebackshield-import-proxy-v1`).digest("hex")
    : null;
  if (process.env.START_RISK_API === "true") {
    const riskService = spawn("python3", ["-m", "uvicorn", "ml.api:app", "--host", "127.0.0.1", "--port", "8001"], {
      cwd: process.cwd(),
      stdio: "ignore",
    });
    riskService.on("error", () => console.error("ChargebackShield risk service could not start."));
    const stopRiskService = () => riskService.kill();
    process.once("SIGTERM", stopRiskService);
    process.once("SIGINT", stopRiskService);
  }
  const app = express();
  const server = createServer(app);
  // Configure body parser with larger size limit for file uploads
  app.use(express.json({ limit: "50mb" }));
  app.use(express.urlencoded({ limit: "50mb", extended: true }));
  registerStorageProxy(app);
  registerOAuthRoutes(app);
  app.use("/risk-api", async (req, res) => {
    try {
      const isMultipart = req.is("multipart/form-data");
      const isImportMutation = req.path.startsWith("/imports/") && req.method === "POST";
      const headers: Record<string, string> = { "content-type": req.headers["content-type"] || "application/json" };
      if (isImportMutation) {
        const user = await sdk.authenticateRequest(req).catch(() => null);
        if (!user) {
          res.status(401).json({ detail: "Sign in as an authorized administrator before importing merchant data." });
          return;
        }
        if (user.role !== "admin") {
          res.status(403).json({ detail: "CSV imports are restricted to administrator team members." });
          return;
        }
        if (!importGatewayToken) {
          res.status(503).json({ detail: "Import authorization is not configured on this environment." });
          return;
        }
        headers["x-chargebackshield-import-token"] = importGatewayToken;
        headers["x-chargebackshield-import-role"] = user.role;
        headers["x-chargebackshield-import-actor"] = user.email || user.name || `user:${user.id}`;
      }
      const upstream = await fetch(`http://127.0.0.1:8001${req.originalUrl.replace(/^\/risk-api/, "")}`, {
        method: req.method,
        headers,
        body: ["GET", "HEAD"].includes(req.method) ? undefined : isMultipart ? (req as unknown as BodyInit) : JSON.stringify(req.body ?? {}),
        ...(isMultipart ? { duplex: "half" } : {}),
      });
      const body = Buffer.from(await upstream.arrayBuffer());
      for (const header of ["content-type", "content-disposition", "cache-control"]) {
        const value = upstream.headers.get(header);
        if (value) res.setHeader(header, value);
      }
      res.status(upstream.status).send(body);
    } catch {
      res.status(503).json({ detail: "Risk service unavailable. Start the FastAPI reference service before generating live evidence." });
    }
  });
  // tRPC API
  app.use(
    "/api/trpc",
    createExpressMiddleware({
      router: appRouter,
      createContext,
    })
  );
  // development mode uses Vite, production mode uses static files
  if (process.env.NODE_ENV === "development") {
    await setupVite(app, server);
  } else {
    serveStatic(app);
  }

  const preferredPort = parseInt(process.env.PORT || "3000");
  const port = await findAvailablePort(preferredPort);

  if (port !== preferredPort) {
    console.log(`Port ${preferredPort} is busy, using port ${port} instead`);
  }

  server.listen(port, () => {
    console.log(`Server running on http://localhost:${port}/`);
  });
}

startServer().catch(console.error);
