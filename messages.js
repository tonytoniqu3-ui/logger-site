// /api/messages.js
// Vercel Serverless Function – Neon (Postgres)
// npm i postgres

const postgres = require("postgres");

// --- 1) Résolution la plus large possible de la connexion Neon ---
const DATABASE_URL =
  process.env.POSTGRES_URL ||                 // Vercel + Neon (courant)
  process.env.DATABASE_URL ||                 // alias fréquent
  process.env.POSTGRES_CONNECTION_STRING ||   // parfois utilisé
  process.env.STORAGE_DATABASE_URL ||         // si passé par "Storage" sur Vercel
  process.env.NEON_DATABASE_URL ||            // autre alias Neon
  process.env.DB_URL ||                       // fallback générique
  "";

// Mieux vaut renvoyer une erreur claire si la variable n'existe pas
if (!DATABASE_URL) {
  module.exports = async (req, res) => {
    res.status(500).json({
      ok: false,
      error:
        "Missing Neon connection string. Tried POSTGRES_URL, DATABASE_URL, POSTGRES_CONNECTION_STRING, STORAGE_DATABASE_URL, NEON_DATABASE_URL, DB_URL",
    });
  };
  return;
}

// --- 2) Création/Réutilisation du client Postgres (serverless-friendly) ---
let sql;
try {
  if (globalThis.__neon_sql__) {
    sql = globalThis.__neon_sql__;
  } else {
    sql = postgres(DATABASE_URL, {
      ssl: "require",
      max: 1, // une seule connexion côté serverless
    });
    globalThis.__neon_sql__ = sql;
  }
} catch (e) {
  // Catch d'init de client
  console.error("Neon client init error:", e);
}

// --- 3) Auto-création de la table ---
async function ensureTable() {
  await sql/*sql*/ `
    CREATE TABLE IF NOT EXISTS messages (
      id           BIGSERIAL PRIMARY KEY,
      created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
      event_type   TEXT,
      user_name    TEXT,
      payload      JSONB,
      ip           TEXT,
      ua           TEXT,
      path         TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
  `;
}

// --- 4) CORS ---
function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

// --- 5) Handler principal ---
module.exports = async (req, res) => {
  try {
    setCors(res);

    if (req.method === "OPTIONS") {
      return res.status(204).end();
    }

    // Sécurité si jamais le client n'a pas été construit
    if (!sql) {
      return res.status(500).json({
        ok: false,
        error: "Neon client not initialized (check DATABASE_URL on Vercel).",
      });
    }

    await ensureTable();

    if (req.method === "GET") {
      const limit = Math.min(
        200,
        Math.max(1, parseInt(req.query.limit || "50", 10))
      );
      const rows = await sql/*sql*/ `
        SELECT id, created_at, event_type, user_name, payload, ip, ua, path
        FROM messages
        ORDER BY created_at DESC
        LIMIT ${limit}
      `;
      return res.status(200).json({ ok: true, rows });
    }

    if (req.method === "POST") {
      // lecture robuste du body
      let body = {};
      try {
        if (req.body && typeof req.body === "object") {
          body = req.body;
        } else {
          // Vercel peut livrer en string si pas d'en-tête JSON correct
          const raw = await new Promise((resolve) => {
            let data = "";
            req.on("data", (c) => (data += c));
            req.on("end", () => resolve(data || "{}"));
          });
          body = JSON.parse(raw);
        }
      } catch {
        body = {};
      }

      const event_type = body.event_type || null;
      const user_name = body.user_name || null;
      const payload = body.payload || body || null;

      const ip =
        req.headers["x-forwarded-for"]?.split(",")[0]?.trim() ||
        req.socket?.remoteAddress ||
        null;
      const ua = req.headers["user-agent"] || null;
      const path =
        body.path ||
        req.headers["x-vercel-deployment-url"] ||
        req.url ||
        null;

      await sql/*sql*/ `
        INSERT INTO messages (event_type, user_name, payload, ip, ua, path)
        VALUES (${event_type}, ${user_name}, ${payload}, ${ip}, ${ua}, ${path})
      `;

      return res.status(201).json({ ok: true });
    }

    return res.status(405).json({ ok: false, error: "Method Not Allowed" });
  } catch (err) {
    console.error("API /api/messages error:", err);
    return res
      .status(500)
      .json({ ok: false, error: String(err?.message || err) });
  }
};
