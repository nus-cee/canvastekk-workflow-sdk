import { timingSafeEqual } from "node:crypto";
import type { Request, Response, NextFunction } from "express";

function isDevMode(): boolean {
  return ["true", "1", "yes"].includes(
    (process.env.CANVASTEKK_DEV_MODE ?? "").toLowerCase(),
  );
}

/** Authentication result. */
export interface AuthResult {
  authMode: string;
  payload?: Record<string, unknown>;
}

/** Express middleware function for authentication. */
export type AuthMiddleware = (
  req: Request,
  res: Response,
  next: NextFunction,
) => void;

function unauthorized(res: Response, detail: string): void {
  res.status(401).json({ detail });
}

/**
 * Authentication middleware for CanvasTEKK nodes.
 */
export class NodeAuth {
  /**
   * Creates API key authentication middleware.
   * @param keyEnvVar - Environment variable name for API key
   * @returns Express middleware function
   */
  static apiKey(keyEnvVar = "CANVASTEKK_API_KEY"): AuthMiddleware {
    return (_req: Request, res: Response, next: NextFunction) => {
      const req = _req as Request;
      if (isDevMode()) {
        next();
        return;
      }

      const expectedKey = process.env[keyEnvVar] ?? "";
      if (!expectedKey) {
        unauthorized(res, "Authentication not configured");
        return;
      }

      const providedKey = req.headers["x-api-key"] as string ?? "";
      const expected = Buffer.from(expectedKey);
      const provided = Buffer.from(providedKey);

      if (expected.length !== provided.length || !timingSafeEqual(provided, expected)) {
        unauthorized(res, "Invalid API key");
        return;
      }

      next();
    };
  }

  /**
   * Creates JWT authentication middleware.
   * @param opts - JWT options including secret variable and algorithm
   * @returns Express middleware function
   */
  static jwt(opts?: {
    secretEnvVar?: string;
    algorithm?: string;
    audience?: string;
  }): AuthMiddleware {
    const secretEnvVar = opts?.secretEnvVar ?? "CANVASTEKK_JWT_SECRET";
    const algorithm = opts?.algorithm ?? "HS256";
    const audience = opts?.audience;

    return async (req: Request, res: Response, next: NextFunction) => {
      if (isDevMode()) {
        next();
        return;
      }

      const secret = process.env[secretEnvVar] ?? "";
      if (!secret) {
        unauthorized(res, "JWT authentication not configured");
        return;
      }

      const authHeader = req.headers.authorization ?? "";
      if (!authHeader.startsWith("Bearer ")) {
        unauthorized(res, "Missing Bearer token");
        return;
      }

      const token = authHeader.substring(7);

      try {
        const jwt = await import("jsonwebtoken");
        const decodeOpts: Record<string, unknown> = { algorithms: [algorithm] };
        if (audience) decodeOpts.audience = audience;
        jwt.verify(token, secret, decodeOpts);
        next();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("expire")) {
          unauthorized(res, "Token has expired");
        } else {
          unauthorized(res, `Invalid token: ${msg}`);
        }
      }
    };
  }

  /**
   * Creates Keycloak JWT authentication middleware.
   * @param opts - Keycloak options including server URL and realm
   * @returns Express middleware function
   */
  static keycloak(opts?: {
    serverUrl?: string;
    realm?: string;
    audience?: string;
    algorithm?: string;
  }): AuthMiddleware {
    const serverUrl = opts?.serverUrl ?? process.env.CANVASTEKK_KEYCLOAK_SERVER_URL ?? "";
    const realm = opts?.realm ?? process.env.CANVASTEKK_KEYCLOAK_REALM ?? "";
    const audience = opts?.audience ?? process.env.CANVASTEKK_KEYCLOAK_AUDIENCE;
    const algorithm = opts?.algorithm ?? "RS256";

    let jwksKeys: Map<string, string> | null = null;
    let jwksFetchedAt = 0;
    const jwksTtl = 300_000;

    function b64ToPem(b64: string): string {
      const lines: string[] = [];
      for (let i = 0; i < b64.length; i += 64) {
        lines.push(b64.slice(i, i + 64));
      }
      return `-----BEGIN CERTIFICATE-----\n${lines.join("\n")}\n-----END CERTIFICATE-----`;
    }

    async function fetchJwks(): Promise<Map<string, string>> {
      if (!serverUrl || !realm) {
        throw new Error("Keycloak server URL and realm must be configured");
      }
      const jwksUrl = `${serverUrl.replace(/\/$/, "")}/realms/${realm}/protocol/openid-connect/certs`;
      const resp = await fetch(jwksUrl, { signal: AbortSignal.timeout(10_000) });
      if (!resp.ok) throw new Error(`Failed to fetch JWKS: HTTP ${resp.status}`);
      const data = await resp.json() as { keys?: Array<{ kid?: string; x5c?: string[]; n?: string; e?: string; kty?: string }> };
      const map = new Map<string, string>();
      if (data.keys) {
        for (const key of data.keys) {
          if (key.kid && key.x5c?.[0]) {
            map.set(key.kid, b64ToPem(key.x5c[0]));
          }
        }
      }
      return map;
    }

    return async (req: Request, res: Response, next: NextFunction) => {
      if (isDevMode()) {
        next();
        return;
      }

      const authHeader = req.headers.authorization ?? "";
      if (!authHeader.startsWith("Bearer ")) {
        unauthorized(res, "Missing Bearer token");
        return;
      }

      const token = authHeader.substring(7);

      try {
        const jwt = await import("jsonwebtoken") as unknown as {
          verify: (token: string, secretOrPublicKey: string, options?: Record<string, unknown>) => unknown;
          decode: (token: string, options?: Record<string, unknown>) => { header?: { kid?: string } } | null;
        };

        const now = Date.now();
        if (!jwksKeys || (now - jwksFetchedAt) > jwksTtl) {
          jwksKeys = await fetchJwks();
          jwksFetchedAt = now;
        }

        const decoded = jwt.decode(token, { complete: true });
        const kid = decoded?.header?.kid;

        let signingKey: string;
        if (kid && jwksKeys.has(kid)) {
          signingKey = jwksKeys.get(kid)!;
        } else if (jwksKeys.size > 0) {
          signingKey = jwksKeys.values().next().value!;
        } else {
          unauthorized(res, "No signing keys available from JWKS");
          return;
        }

        const decodeOpts: Record<string, unknown> = { algorithms: [algorithm] };
        if (audience) decodeOpts.audience = audience;
        jwt.verify(token, signingKey, decodeOpts);
        next();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        unauthorized(res, `Invalid token: ${msg}`);
      }
    };
  }
}
