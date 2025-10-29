// /api/messages.js
const postgres = require("postgres");

// Connexion à la base Neon
const sql = postgres(process.env.POSTGRES_URL, {
  ssl: "require",
  max: 1, // compatible serverless
});

// Création automatique de la table au premier appel
async function ensureTable() {
  await sql/*sql*/`
    CREATE TABLE IF NOT EXISTS messages (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      event_type TEXT,
      user_name TEXT,
      payload JSONB,
      ip TEXT,
      ua TEXT,
      path TEXT
    );
  `;
}

// CORS
function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

// Handler principal
module.exports = async (req, res) => {
  try {
    setCors(res);

    if (req.method === "OPTIONS") {
      return res.status(204).end();
    }

    await ensureTable();

    // Lecture
    if (req.method === "GET") {
      const limit = Math.min(200, parseInt(req.query.limit || "50", 10));
      const rows = await sql/*sql*/`
        SELECT id, created_at, event_type, user_name, payload, ip, ua, path
        FROM messages
        ORDER BY created_at DESC
        LIMIT ${limit};
      `;
      return res.status(200).json({ ok: true, rows });
    }

    // Écriture
    if (req.method === "POST") {
      const body =
        typeof req.body === "object"
          ? req.body
          : (() => {
              try {
                return JSON.parse(req.body || "{}");
              } catch {
                return {};
              }
            })();

      const { event_type, user_name, payload } = body;

      const ip =
        req.headers["x-forwarded-for"]?.split(",")[0]?.trim() ||
        req.socket?.remoteAddress ||
        null;
      const ua = req.headers["user-agent"] || null;
      const path =
        body.path || req.headers["x-vercel-deployment-url"] || req.url || null;

      await sql/*sql*/`
        INSERT INTO messages (event_type, user_name, payload, ip, ua, path)
        VALUES (${event_type}, ${user_name}, ${payload}, ${ip}, ${ua}, ${path});
      `;

      return res.status(201).json({ ok: true });
    }

    res.status(405).json({ ok: false, error: "Method Not Allowed" });
  } catch (err) {
    console.error("API /api/messages error:", err);
    res.status(500).json({ ok: false, error: String(err?.message || err) });
  }
};
