// api/messages.js
// Vercel Serverless Function — Neon (Postgres)
// npm i postgres

const postgres = require("postgres");

// 1) Connexion (utilise ta variable POSTGRES_URL définie dans Vercel)
const POSTGRES_URL =
  process.env.POSTGRES_URL ||
  process.env.DATABASE_URL ||
  process.env.POSTGRES_CONNECTION_STRING;

if (!POSTGRES_URL) {
  module.exports = async (req, res) => {
    res.status(500).json({ ok: false, error: "Missing POSTGRES_URL env var" });
  };
  return;
}

const sql = postgres(POSTGRES_URL, { ssl: "require", max: 1 });

// 2) Création de table si besoin
async function ensureTable() {
  await sql/*sql*/`
    CREATE TABLE IF NOT EXISTS messages (
      id         BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      event_type TEXT,
      user_name  TEXT,
      payload    JSONB,
      ip         TEXT,
      ua         TEXT,
      path       TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
  `;
}

// 3) CORS
function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

// 4) Handler
module.exports = async (req, res) => {
  try {
    setCors(res);
    if (req.method === "OPTIONS") return res.status(204).end();

    await ensureTable();

    if (req.method === "GET") {
      const limit = Math.min(200, Math.max(1, parseInt(req.query.limit || "50", 10)));
      const rows = await sql/*sql*/`
        SELECT id, created_at, event_type, user_name, payload, ip, ua, path
        FROM messages
        ORDER BY created_at DESC
        LIMIT ${limit}
      `;
      return res.status(200).json({ ok: true, rows });
    }

    if (req.method === "POST") {
      const body = (req.body && typeof req.body === "object")
        ? req.body
        : (() => { try { return JSON.parse(req.body || "{}"); } catch { return {}; } })();

      const event_type = body.event_type || null;
      const user_name  = body.user_name  || null;
      const payload    = body.payload    || null;

      const ip = req.headers["x-forwarded-for"]?.split(",")[0]?.trim()
              || req.socket?.remoteAddress || null;
      const ua   = req.headers["user-agent"] || null;
      const path = body.path || req.url || null;

      await sql/*sql*/`
        INSERT INTO messages (event_type, user_name, payload, ip, ua, path)
        VALUES (${event_type}, ${user_name}, ${payload}, ${ip}, ${ua}, ${path})
      `;

      return res.status(201).json({ ok: true });
    }

    return res.status(405).json({ ok: false, error: "Method Not Allowed" });
  } catch (err) {
    console.error("API /api/messages error:", err);
    return res.status(500).json({ ok: false, error: String(err?.message || err) });
  }
};
