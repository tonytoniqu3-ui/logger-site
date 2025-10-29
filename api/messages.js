// /api/messages.js
const postgres = require("postgres");

const sql = postgres(process.env.POSTGRES_URL, {
  ssl: "require",
  max: 1, // serverless-friendly
});

module.exports = async (req, res) => {
  try {
    // Test simple : ping de la base Neon
    const row = await sql`select now() as now`;
    res.status(200).json({ ok: true, now: row[0].now });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err && err.message || err) });
  }
};
