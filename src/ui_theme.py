def inject_theme() -> str:
    return """
<style>
:root {
  --bg-a: #f3f8ff;
  --bg-b: #e8f4ee;
  --glass: rgba(255,255,255,0.72);
  --line: rgba(16,42,67,0.12);
  --text: #102a43;
  --accent: #1565c0;
  --accent2: #00897b;
}
.stApp {
  background: radial-gradient(circle at 15% 10%, var(--bg-a), #ffffff 48%),
              radial-gradient(circle at 80% 20%, var(--bg-b), transparent 45%);
}
.block-container {
  padding-top: 1.2rem;
  max-width: 1250px;
}
.hero {
  padding: 1rem 1.2rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--glass);
  backdrop-filter: blur(8px);
  margin-bottom: 0.8rem;
}
.metric-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #ffffff;
  padding: 0.7rem;
}
.badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.1rem 0.55rem;
  font-size: 0.76rem;
  border: 1px solid var(--line);
}
.badge-rec { background: #e9f6ff; color: #0b63b1; }
.badge-vip { background: #e8f7f3; color: #087264; }
.badge-warn { background: #fff3e5; color: #a35700; }
@media (max-width: 900px) {
  .block-container { padding-top: 0.5rem; }
}
</style>
"""
