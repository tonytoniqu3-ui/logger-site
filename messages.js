const postgres = require("postgres");

const sql = postgres(process.env.POSTGRES_URL, {
  ssl: "require",
  max: 1
});

function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

module.exports = async (req, res) => {
  setCors(res);

  if (req.method === "OPTIONS") return res.status(200).end();

  try {
    await sql/* sql */`
      CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        text TEXT,
        user_name TEXT,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        email TEXT,
        gender TEXT,
        nationality TEXT,
        age INT,
        height_cm INT,
        page TEXT,
        ua TEXT,
        ip TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );
    `;

    if (req.method === "POST") {
      let body = {};
      const ct = (req.headers["content-type"] || "").toLowerCase();
      if (ct.includes("application/json")) body = req.body || {};
      else if (ct.includes("application/x-www-form-urlencoded")) {
        const raw = await getRawBody(req);
        body = Object.fromEntries(new URLSearchParams(raw));
      }

      const { text, user, firstName, lastName, phone, email, gender, nationality, age, height, page } = body;
      const ua = req.headers["user-agent"] || "";
      const ip = (req.headers["x-forwarded-for"] || "").split(",")[0] || req.socket?.remoteAddress || "";

      await sql/* sql */`
        INSERT INTO messages
          (text, user_name, first_name, last_name, phone, email, gender, nationality, age, height_cm, page, ua, ip)
        VALUES
          (${text || null}, ${user || null}, ${firstName || null}, ${lastName || null}, ${phone || null},
           ${email || null}, ${gender || null}, ${nationality || null}, ${parseInt(age) || null},
           ${parseInt(height) || null}, ${page || null}, ${ua}, ${ip});
      `;

      return res.status(200).json({ ok: true });
    }

    if (req.method === "GET") {
      const limit = Math.min(parseInt(req.query.limit || "50", 10), 500);
      const rows = await sql/* sql */`
        SELECT * FROM messages ORDER BY created_at DESC LIMIT ${limit};
      `;
      return res.status(200).json({ ok: true, rows });
    }

    res.setHeader("Allow", "GET, POST, OPTIONS");
    return res.status(405).end();
  } catch (err) {
    console.error(err);
    return res.status(500).json({ ok: false, error: err.message });
  }
};

function getRawBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}
