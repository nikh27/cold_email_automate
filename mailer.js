/**
 * mailer.js — Node.js HTTP microservice for sending emails via Gmail SMTP
 * Exactly like your friend's nodemailer code, but as a tiny HTTP server.
 * Python Flask app calls this on port 3001 to send each email.
 */

const nodemailer = require("nodemailer");
const express    = require("express");
const fs         = require("fs");
const path       = require("path");

const app  = express();
app.use(express.json({ limit: "10mb" }));

const PORT = process.env.MAILER_PORT || 3001;

// ── Create Gmail transporter (exactly like your friend's code) ───────────────
const createTransporter = () => {
    return nodemailer.createTransport({
        host:   "smtp.gmail.com",
        port:   587,
        secure: false,
        auth: {
            user: process.env.GMAIL_USER,
            pass: process.env.GMAIL_APP_PASSWORD
        },
        tls: { rejectUnauthorized: false }
    });
};

// ── Health check ─────────────────────────────────────────────────────────────
app.get("/health", (req, res) => {
    res.json({
        status:     "alive",
        gmail_user: process.env.GMAIL_USER || "NOT SET",
        password_set: !!(process.env.GMAIL_APP_PASSWORD)
    });
});

// ── Send one email ────────────────────────────────────────────────────────────
// POST /send
// Body: { to, subject, body, resume_path }
app.post("/send", async (req, res) => {
    const { to, subject, body, resume_path } = req.body;

    if (!to || !subject || !body) {
        return res.status(400).json({ success: false, error: "Missing to/subject/body" });
    }

    if (!process.env.GMAIL_USER || !process.env.GMAIL_APP_PASSWORD) {
        return res.status(500).json({ success: false, error: "Gmail credentials not set in environment" });
    }

    try {
        const transporter = createTransporter();

        const mailOptions = {
            from:    `"Soumya Kumari" <${process.env.GMAIL_USER}>`,
            to:      to,
            subject: subject,
            text:    body,
        };

        // Attach resume if it exists
        if (resume_path && fs.existsSync(resume_path)) {
            mailOptions.attachments = [{
                filename: "Soumya_Kumari_Resume.pdf",
                path:     resume_path
            }];
        }

        const info = await transporter.sendMail(mailOptions);
        console.log(`✅ Sent → ${to} | ${info.response}`);
        res.json({ success: true, response: info.response });

    } catch (err) {
        console.log(`❌ Failed → ${to} | ${err.message}`);
        res.status(500).json({ success: false, error: err.message });
    }
});

// ── Test endpoint (sends 1 test email to yourself) ────────────────────────────
app.post("/test", async (req, res) => {
    const testTo = process.env.GMAIL_USER;
    try {
        const transporter = createTransporter();
        const info = await transporter.sendMail({
            from:    `"Soumya Kumari" <${process.env.GMAIL_USER}>`,
            to:      testTo,
            subject: "✅ Node.js Mailer Test — Cold Email System",
            text:    "If you are reading this, the Node.js mailer is working perfectly on the cloud server! 🎉"
        });
        console.log(`✅ Test email sent: ${info.response}`);
        res.json({ success: true, message: "Test email sent!", to: testTo });
    } catch (err) {
        console.log(`❌ Test failed: ${err.message}`);
        res.status(500).json({ success: false, error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`📮 Node.js mailer running on port ${PORT}`);
    console.log(`   Gmail user: ${process.env.GMAIL_USER || "NOT SET"}`);
});
