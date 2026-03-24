# core/ai/integrations.py
# Complete integrations library - every domain, working code patterns
# Auto-detected from project description and injected into generation prompts

INTEGRATIONS = {

    # ── AUTH ──────────────────────────────────────────────────────
    "clerk": {
        "keywords": ["auth", "login", "signup", "user", "account", "clerk"],
        "packages_frontend": ["@clerk/clerk-react"],
        "packages_backend": [],
        "env_frontend": {"VITE_CLERK_PUBLISHABLE_KEY": "pk_test_your_key_here"},
        "env_backend": {},
        "docs_url": "https://clerk.com",
        "prompt": """
CLERK AUTH (Frontend Only - v5):
main.jsx:
  import { ClerkProvider } from '@clerk/clerk-react'
  const appearance = { variables: { colorPrimary: '#f0c040', colorBackground: '#050505', colorInputBackground: '#141414', colorText: '#f0ede8', borderRadius: '10px' }, elements: { card: 'background:rgba(12,12,12,0.92);border:1px solid rgba(255,255,255,0.08)', formButtonPrimary: 'background:#f0c040;color:#050505;font-weight:600' }}
  <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY} appearance={appearance}>

App.jsx routes:
  /sign-in/* -> <SignIn routing="path" path="/sign-in" afterSignInUrl="/" />
  /sign-up/* -> <SignUp routing="path" path="/sign-up" afterSignUpUrl="/" />
  Protected: <SignedIn>content</SignedIn><SignedOut><RedirectToSignIn /></SignedOut>
  Navbar: <SignedIn><UserButton /></SignedIn><SignedOut><SignInButton mode="modal"><button className="btn btn-primary btn-sm">Sign In</button></SignInButton></SignedOut>

Backend auth (no packages needed):
  def get_user_id():
      auth = request.headers.get('Authorization', '')
      if not auth.startswith('Bearer '): return None
      try:
          import base64, json
          payload = auth.split(' ')[1].split('.')[1]
          payload += '=' * (4 - len(payload) % 4)
          return json.loads(base64.b64decode(payload)).get('sub')
      except: return None
"""
    },

    # ── PAYMENTS ──────────────────────────────────────────────────
    "stripe": {
        "keywords": ["payment", "stripe", "subscription", "billing", "checkout", "pricing", "plan", "purchase", "buy", "paid"],
        "packages_frontend": ["@stripe/stripe-js", "@stripe/react-stripe-js"],
        "packages_backend": ["stripe==8.0.0"],
        "env_frontend": {"VITE_STRIPE_PUBLISHABLE_KEY": "pk_test_your_key_here"},
        "env_backend": {"STRIPE_SECRET_KEY": "sk_test_your_secret_here", "STRIPE_WEBHOOK_SECRET": "whsec_your_webhook_secret"},
        "docs_url": "https://stripe.com/docs",
        "prompt": """
STRIPE PAYMENTS:
Backend (routes/payments.py):
  import stripe, os
  stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
  from flask import Blueprint, request, jsonify
  payments_bp = Blueprint('payments', __name__)

  @payments_bp.route('/payments/create-checkout', methods=['POST'])
  def create_checkout():
      data = request.get_json()
      session = stripe.checkout.Session.create(
          payment_method_types=['card'],
          line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': data['name']}, 'unit_amount': data['amount']}, 'quantity': 1}],
          mode=data.get('mode', 'payment'),  # 'payment' or 'subscription'
          success_url='http://localhost:5173/success?session_id={CHECKOUT_SESSION_ID}',
          cancel_url='http://localhost:5173/pricing',
      )
      return jsonify({'success': True, 'url': session.url, 'session_id': session.id})

  @payments_bp.route('/payments/webhook', methods=['POST'])
  def webhook():
      try:
          event = stripe.Webhook.construct_event(request.data, request.headers.get('Stripe-Signature'), os.environ.get('STRIPE_WEBHOOK_SECRET'))
          if event['type'] == 'checkout.session.completed':
              pass  # Handle successful payment
          elif event['type'] == 'customer.subscription.updated':
              pass  # Handle subscription change
          return jsonify({'success': True})
      except Exception as e:
          return jsonify({'error': str(e)}), 400

Frontend (hooks/useStripe.js):
  import { loadStripe } from '@stripe/stripe-js'
  const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY)
  export const useCheckout = () => {
    const [loading, setLoading] = useState(false)
    const checkout = async (name, amount, mode='payment') => {
      setLoading(true)
      try {
        const res = await api.post('/payments/create-checkout', {name, amount: amount*100, mode})
        window.location.href = res.data.url
      } finally { setLoading(false) }
    }
    return { checkout, loading }
  }
"""
    },

    # ── EMAIL ─────────────────────────────────────────────────────
    "email": {
        "keywords": ["email", "mail", "send", "notify", "notification", "resend", "sendgrid", "smtp"],
        "packages_frontend": [],
        "packages_backend": ["resend==2.0.0"],
        "env_frontend": {},
        "env_backend": {"RESEND_API_KEY": "re_your_key_here", "FROM_EMAIL": "noreply@yourdomain.com"},
        "docs_url": "https://resend.com/docs",
        "prompt": """
EMAIL (Resend - modern email API):
Backend (utils/email.py):
  import resend, os
  resend.api_key = os.environ.get('RESEND_API_KEY')

  def send_email(to: str, subject: str, html: str):
      try:
          resend.Emails.send({'from': os.environ.get('FROM_EMAIL', 'noreply@app.com'), 'to': to, 'subject': subject, 'html': html})
          return True
      except Exception as e:
          print(f'Email error: {e}')
          return False

  def send_welcome(to: str, name: str):
      send_email(to, f'Welcome to the platform, {name}!',
          f'<h1>Welcome {name}</h1><p>Your account is ready.</p>')

  def send_notification(to: str, title: str, message: str):
      send_email(to, title, f'<h2>{title}</h2><p>{message}</p>')
"""
    },

    # ── STORAGE ───────────────────────────────────────────────────
    "storage": {
        "keywords": ["upload", "file", "image", "photo", "storage", "s3", "cdn", "media", "cloudinary"],
        "packages_frontend": [],
        "packages_backend": ["boto3==1.34.0", "python-multipart==0.0.7"],
        "env_frontend": {},
        "env_backend": {
            "AWS_ACCESS_KEY_ID": "your_key",
            "AWS_SECRET_ACCESS_KEY": "your_secret",
            "AWS_BUCKET_NAME": "your_bucket",
            "AWS_REGION": "us-east-1"
        },
        "docs_url": "https://boto3.amazonaws.com/v1/documentation/api/latest/index.html",
        "prompt": """
FILE UPLOAD (S3 / Cloudinary):
Backend (utils/storage.py):
  import boto3, os, uuid
  from werkzeug.utils import secure_filename

  s3 = boto3.client('s3',
      aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
      aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
      region_name=os.environ.get('AWS_REGION', 'us-east-1')
  )
  BUCKET = os.environ.get('AWS_BUCKET_NAME', '')

  def upload_file(file, folder='uploads'):
      filename = f"{folder}/{uuid.uuid4().hex}_{secure_filename(file.filename)}"
      s3.upload_fileobj(file, BUCKET, filename, ExtraArgs={'ACL': 'public-read', 'ContentType': file.content_type})
      return f"https://{BUCKET}.s3.amazonaws.com/{filename}"

Upload route:
  from flask import request, jsonify
  from utils.storage import upload_file
  @bp.route('/upload', methods=['POST'])
  def upload():
      file = request.files.get('file')
      if not file: return jsonify({'error': 'No file'}), 400
      url = upload_file(file)
      return jsonify({'success': True, 'url': url})

Frontend upload component:
  const handleUpload = async (e) => {
    const formData = new FormData()
    formData.append('file', e.target.files[0])
    const res = await fetch('/api/v1/upload', {method: 'POST', body: formData})
    const {url} = await res.json()
    setImageUrl(url)
  }
  <input type="file" onChange={handleUpload} accept="image/*" className="hidden" id="upload" />
  <label htmlFor="upload" className="btn btn-secondary cursor-pointer">Upload Image</label>
"""
    },

    # ── REALTIME ──────────────────────────────────────────────────
    "realtime": {
        "keywords": ["realtime", "real-time", "live", "socket", "websocket", "chat", "notification", "push", "broadcast"],
        "packages_frontend": ["socket.io-client"],
        "packages_backend": ["flask-socketio==5.3.6", "eventlet==0.35.2"],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://flask-socketio.readthedocs.io",
        "prompt": """
REALTIME (Socket.IO):
Backend (app.py addition):
  from flask_socketio import SocketIO, emit, join_room, leave_room
  socketio = SocketIO(app, cors_allowed_origins="*")

  @socketio.on('join')
  def on_join(data): join_room(data['room'])

  @socketio.on('message')
  def on_message(data):
      emit('message', data, room=data['room'])

  if __name__ == '__main__':
      socketio.run(app, debug=True, host='0.0.0.0', port=5000)

Frontend (hooks/useSocket.js):
  import { useEffect, useRef } from 'react'
  import { io } from 'socket.io-client'
  export function useSocket(room) {
    const socket = useRef(null)
    useEffect(() => {
      socket.current = io('http://localhost:5000')
      socket.current.emit('join', {room})
      return () => socket.current.disconnect()
    }, [room])
    const send = (msg) => socket.current?.emit('message', {room, ...msg})
    return { socket: socket.current, send }
  }
"""
    },

    # ── DATABASE: POSTGRES ────────────────────────────────────────
    "postgres": {
        "keywords": ["postgres", "postgresql", "database", "production database"],
        "packages_frontend": [],
        "packages_backend": ["psycopg2-binary==2.9.9"],
        "env_frontend": {},
        "env_backend": {"DATABASE_URL": "postgresql://user:password@localhost:5432/dbname"},
        "docs_url": "https://www.postgresql.org/docs/",
        "prompt": """
POSTGRESQL:
config.py:
  import os
  class Config:
      SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
      # For Railway/Render postgres URLs starting with postgres:// fix to postgresql://
      if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
          SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
"""
    },

    # ── ANALYTICS ─────────────────────────────────────────────────
    "analytics": {
        "keywords": ["analytics", "tracking", "metrics", "events", "posthog", "mixpanel", "amplitude", "stats"],
        "packages_frontend": ["posthog-js"],
        "packages_backend": [],
        "env_frontend": {"VITE_POSTHOG_KEY": "phc_your_key_here", "VITE_POSTHOG_HOST": "https://app.posthog.com"},
        "env_backend": {},
        "docs_url": "https://posthog.com/docs",
        "prompt": """
ANALYTICS (PostHog - open source, free tier):
main.jsx:
  import posthog from 'posthog-js'
  posthog.init(import.meta.env.VITE_POSTHOG_KEY, {api_host: import.meta.env.VITE_POSTHOG_HOST})

Usage in components:
  import posthog from 'posthog-js'
  posthog.capture('button_clicked', {button: 'upgrade', plan: 'pro'})
  posthog.identify(userId, {email: user.email, name: user.name})
  posthog.capture('$pageview')

Feature flags:
  const flagEnabled = posthog.isFeatureEnabled('new-dashboard')
"""
    },

    # ── AI / LLM ──────────────────────────────────────────────────
    "ai": {
        "keywords": ["ai", "llm", "gpt", "openai", "chat", "assistant", "generate", "ml", "intelligence", "groq", "anthropic"],
        "packages_frontend": [],
        "packages_backend": ["openai==1.30.0"],
        "env_frontend": {},
        "env_backend": {"OPENAI_API_KEY": "sk-your_key_here"},
        "docs_url": "https://platform.openai.com/docs",
        "prompt": """
AI INTEGRATION (OpenAI / Groq compatible):
Backend (utils/ai.py):
  from openai import OpenAI
  import os
  client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

  def chat_complete(messages: list, model='gpt-4o-mini', max_tokens=1000) -> str:
      response = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens)
      return response.choices[0].message.content

  def stream_complete(messages: list, model='gpt-4o-mini'):
      stream = client.chat.completions.create(model=model, messages=messages, stream=True)
      for chunk in stream:
          if chunk.choices[0].delta.content:
              yield chunk.choices[0].delta.content

AI route with streaming:
  from flask import Response, stream_with_context
  @bp.route('/ai/chat', methods=['POST'])
  def ai_chat():
      data = request.get_json()
      messages = data.get('messages', [])
      def generate():
          for chunk in stream_complete(messages):
              yield f'data: {chunk}\\n\\n'
      return Response(stream_with_context(generate()), mimetype='text/event-stream')

Frontend streaming hook:
  const streamChat = async (messages, onChunk) => {
    const res = await fetch('/api/v1/ai/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({messages})})
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const {done, value} = await reader.read()
      if (done) break
      const chunk = decoder.decode(value).replace('data: ', '').trim()
      if (chunk) onChunk(chunk)
    }
  }
"""
    },

    # ── SEARCH ────────────────────────────────────────────────────
    "search": {
        "keywords": ["search", "full text", "elasticsearch", "algolia", "typesense", "filter", "query"],
        "packages_frontend": [],
        "packages_backend": ["flask-sqlalchemy==3.1.1"],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "",
        "prompt": """
SEARCH (SQLite full-text / PostgreSQL):
Backend search route:
  @bp.route('/search', methods=['GET'])
  def search():
      q = request.args.get('q', '').strip()
      page = int(request.args.get('page', 1))
      per_page = int(request.args.get('per_page', 20))
      if not q:
          return jsonify({'success': True, 'data': [], 'total': 0})
      # SQLAlchemy ilike for case-insensitive search
      results = Item.query.filter(
          db.or_(Item.name.ilike(f'%{q}%'), Item.description.ilike(f'%{q}%'))
      ).paginate(page=page, per_page=per_page, error_out=False)
      return jsonify({'success': True, 'data': [r.to_dict() for r in results.items], 'total': results.total, 'pages': results.pages})

Frontend search:
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  
  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await api.get(`/search?q=${encodeURIComponent(query)}`)
        setResults(res.data.data)
      } finally { setLoading(false) }
    }, 300) // debounce 300ms
    return () => clearTimeout(timer)
  }, [query])
"""
    },

    # ── OAUTH / SOCIAL ────────────────────────────────────────────
    "oauth": {
        "keywords": ["google", "github", "oauth", "social login", "sso"],
        "packages_frontend": [],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "",
        "prompt": """
OAUTH (Handled by Clerk - no extra code needed):
  Clerk automatically handles Google, GitHub, Discord, Twitter OAuth.
  Enable providers in Clerk Dashboard -> User & Authentication -> Social Connections.
  No backend code required - Clerk manages all OAuth flows.
"""
    },

    # ── RATE LIMITING ─────────────────────────────────────────────
    "ratelimit": {
        "keywords": ["rate limit", "throttle", "limit", "api rate"],
        "packages_frontend": [],
        "packages_backend": ["flask-limiter==3.5.0"],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://flask-limiter.readthedocs.io",
        "prompt": """
RATE LIMITING:
app.py:
  from flask_limiter import Limiter
  from flask_limiter.util import get_remote_address
  limiter = Limiter(app=app, key_func=get_remote_address, default_limits=['200/day', '50/hour'])

On specific routes:
  @bp.route('/api/heavy-endpoint', methods=['POST'])
  @limiter.limit('10/minute')
  def heavy_endpoint(): ...
"""
    },

    # ── CACHING ───────────────────────────────────────────────────
    "cache": {
        "keywords": ["cache", "caching", "redis", "performance", "fast"],
        "packages_frontend": [],
        "packages_backend": ["flask-caching==2.1.0"],
        "env_frontend": {},
        "env_backend": {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": "300"},
        "docs_url": "https://flask-caching.readthedocs.io",
        "prompt": """
CACHING:
app.py:
  from flask_caching import Cache
  cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

Usage:
  @bp.route('/data')
  @cache.cached(timeout=60, key_prefix='all_items')
  def get_data():
      return jsonify(expensive_db_query())

  # Invalidate cache
  cache.delete('all_items')
"""
    },

    # ── NOTIFICATIONS ─────────────────────────────────────────────
    "notifications": {
        "keywords": ["notification", "push", "alert", "toast", "bell", "notify"],
        "packages_frontend": [],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "",
        "prompt": """
IN-APP NOTIFICATIONS (database-backed):
Model:
  class Notification(db.Model):
      id = db.Column(db.Integer, primary_key=True)
      user_id = db.Column(db.String(255), nullable=False, index=True)
      title = db.Column(db.String(255), nullable=False)
      message = db.Column(db.Text)
      type = db.Column(db.String(50), default='info')  # info, success, warning, error
      read = db.Column(db.Boolean, default=False)
      created_at = db.Column(db.DateTime, default=datetime.utcnow)
      def to_dict(self):
          return {'id': self.id, 'title': self.title, 'message': self.message, 'type': self.type, 'read': self.read, 'created_at': self.created_at.isoformat()}

Routes:
  GET  /notifications - get all unread
  PUT  /notifications/:id/read - mark as read
  POST /notifications/mark-all-read - mark all read

Frontend NotificationBell:
  const {data} = useQuery('/notifications')
  const unread = data?.filter(n => !n.read).length || 0
  <button className="btn btn-ghost btn-icon" style={{position:'relative'}}>
    <Bell size={18}/>
    {unread > 0 && <span style={{position:'absolute',top:4,right:4,width:8,height:8,background:'var(--red)',borderRadius:'50%'}}/>}
  </button>
"""
    },

    # ── CHARTS / VISUALIZATION ────────────────────────────────────
    "charts": {
        "keywords": ["chart", "graph", "dashboard", "analytics", "visualization", "recharts", "chart.js", "stats", "metrics"],
        "packages_frontend": ["recharts"],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://recharts.org",
        "prompt": """
CHARTS (Recharts):
  import { LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

Line chart:
  <ResponsiveContainer width="100%" height={280}>
    <LineChart data={data}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
      <XAxis dataKey="name" stroke="#444" tick={{fill:'#666',fontSize:11}}/>
      <YAxis stroke="#444" tick={{fill:'#666',fontSize:11}}/>
      <Tooltip contentStyle={{background:'#141414',border:'1px solid rgba(255,255,255,0.08)',borderRadius:10}}/>
      <Line type="monotone" dataKey="value" stroke="#f0c040" strokeWidth={2} dot={false} activeDot={{r:4,fill:'#f0c040'}}/>
    </LineChart>
  </ResponsiveContainer>

Bar chart:
  <BarChart data={data}>
    <Bar dataKey="value" fill="#f0c040" radius={[4,4,0,0]}/>
  </BarChart>

Pie chart:
  <PieChart><Pie data={data} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value">
    {data.map((_,i) => <Cell key={i} fill={['#f0c040','#34d399','#60a5fa','#f87171'][i%4]}/>)}
  </Pie></PieChart>
"""
    },

    # ── MAPS ──────────────────────────────────────────────────────
    "maps": {
        "keywords": ["map", "maps", "location", "geo", "coordinates", "leaflet", "mapbox", "google maps"],
        "packages_frontend": ["leaflet", "react-leaflet"],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://react-leaflet.js.org",
        "prompt": """
MAPS (React Leaflet - free, no API key needed):
  import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
  import 'leaflet/dist/leaflet.css'
  import L from 'leaflet'
  // Fix default marker icons
  delete L.Icon.Default.prototype._getIconUrl
  L.Icon.Default.mergeOptions({iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'), iconUrl: require('leaflet/dist/images/marker-icon.png'), shadowUrl: require('leaflet/dist/images/marker-shadow.png')})
  
  <MapContainer center={[51.505, -0.09]} zoom={13} style={{height:'400px',borderRadius:'var(--r-lg)'}}>
    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="OpenStreetMap"/>
    <Marker position={[51.505, -0.09]}>
      <Popup>A marker popup</Popup>
    </Marker>
  </MapContainer>
"""
    },

    # ── EXPORT / PDF ──────────────────────────────────────────────
    "export": {
        "keywords": ["export", "pdf", "download", "report", "csv", "excel"],
        "packages_frontend": [],
        "packages_backend": ["reportlab==4.1.0"],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://www.reportlab.com/docs/reportlab-userguide.pdf",
        "prompt": """
EXPORT (CSV + PDF):
CSV export:
  import csv, io
  from flask import Response
  @bp.route('/export/csv')
  def export_csv():
      items = Item.query.all()
      output = io.StringIO()
      writer = csv.DictWriter(output, fieldnames=['id','name','created_at'])
      writer.writeheader()
      writer.writerows([i.to_dict() for i in items])
      return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=export.csv'})

Frontend download button:
  <a href="/api/v1/export/csv" download className="btn btn-secondary btn-sm">
    <Download size={14}/> Export CSV
  </a>
"""
    },

    # ── WEBHOOKS ──────────────────────────────────────────────────
    "webhooks": {
        "keywords": ["webhook", "event", "trigger", "callback", "integration"],
        "packages_frontend": [],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {"WEBHOOK_SECRET": "your_webhook_secret"},
        "docs_url": "",
        "prompt": """
WEBHOOKS:
Backend webhook receiver:
  import hmac, hashlib, os
  @bp.route('/webhooks/receive', methods=['POST'])
  def receive_webhook():
      # Verify signature
      sig = request.headers.get('X-Webhook-Signature', '')
      expected = hmac.new(os.environ.get('WEBHOOK_SECRET','').encode(), request.data, hashlib.sha256).hexdigest()
      if not hmac.compare_digest(sig, f'sha256={expected}'):
          return jsonify({'error': 'Invalid signature'}), 401
      event = request.get_json()
      print(f"Webhook received: {event.get('type')}")
      return jsonify({'success': True})
"""
    },

    # ── DARK MODE ─────────────────────────────────────────────────
    "darkmode": {
        "keywords": ["dark mode", "theme", "light mode", "toggle theme"],
        "packages_frontend": [],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "",
        "prompt": """
THEME TOGGLE (Dark/Light):
hooks/useTheme.js:
  import { useState, useEffect } from 'react'
  export function useTheme() {
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')
    useEffect(() => {
      document.documentElement.setAttribute('data-theme', theme)
      localStorage.setItem('theme', theme)
    }, [theme])
    const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark')
    return { theme, toggle, isDark: theme === 'dark' }
  }

CSS (add to index.css):
  [data-theme="light"] {
    --bg: #f8f8f8; --surface: #ffffff; --surface-2: #f0f0f0;
    --border: rgba(0,0,0,0.08); --text: #111; --text-2: #555; --text-3: #999;
  }
"""
    },

    # ── MARKDOWN ──────────────────────────────────────────────────
    "markdown": {
        "keywords": ["markdown", "blog", "content", "editor", "rich text", "notes", "docs"],
        "packages_frontend": ["react-markdown", "remark-gfm"],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://github.com/remarkjs/react-markdown",
        "prompt": """
MARKDOWN RENDERING:
  import ReactMarkdown from 'react-markdown'
  import remarkGfm from 'remark-gfm'
  
  <ReactMarkdown remarkPlugins={[remarkGfm]}
    components={{
      h1: ({children}) => <h1 style={{fontFamily:'var(--font-display)',marginBottom:16}}>{children}</h1>,
      p: ({children}) => <p style={{marginBottom:16,lineHeight:1.75,color:'var(--text-2)'}}>{children}</p>,
      code: ({children}) => <code style={{background:'var(--surface-2)',padding:'2px 6px',borderRadius:4,fontFamily:'monospace'}}>{children}</code>,
      a: ({href,children}) => <a href={href} style={{color:'var(--accent)'}}>{children}</a>,
    }}>
    {content}
  </ReactMarkdown>
"""
    },

    # ── DRAG AND DROP ─────────────────────────────────────────────
    "dnd": {
        "keywords": ["drag", "drop", "kanban", "board", "reorder", "sortable"],
        "packages_frontend": ["@dnd-kit/core", "@dnd-kit/sortable"],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://dndkit.com",
        "prompt": """
DRAG AND DROP (@dnd-kit):
  import { DndContext, closestCenter } from '@dnd-kit/core'
  import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable'
  import { CSS } from '@dnd-kit/utilities'

  function SortableItem({id, children}) {
    const {attributes, listeners, setNodeRef, transform, transition} = useSortable({id})
    const style = {transform: CSS.Transform.toString(transform), transition, cursor: 'grab'}
    return <div ref={setNodeRef} style={style} {...attributes} {...listeners}>{children}</div>
  }

  function SortableList({items, setItems}) {
    const handleDragEnd = ({active, over}) => {
      if (active.id !== over?.id) {
        const oldIdx = items.findIndex(i => i.id === active.id)
        const newIdx = items.findIndex(i => i.id === over.id)
        setItems(arrayMove(items, oldIdx, newIdx))
      }
    }
    return (
      <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
          {items.map(item => <SortableItem key={item.id} id={item.id}>{item.name}</SortableItem>)}
        </SortableContext>
      </DndContext>
    )
  }
"""
    },

    # ── CALENDAR ──────────────────────────────────────────────────
    "calendar": {
        "keywords": ["calendar", "schedule", "event", "booking", "appointment", "date picker"],
        "packages_frontend": ["react-datepicker"],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://reactdatepicker.com",
        "prompt": """
DATE PICKER (react-datepicker):
  import DatePicker from 'react-datepicker'
  import 'react-datepicker/dist/react-datepicker.css'
  
  const [date, setDate] = useState(new Date())
  <DatePicker selected={date} onChange={setDate}
    className="input" dateFormat="MMM d, yyyy"
    wrapperClassName="w-full"
    popperPlacement="bottom-start" />
"""
    },

    # ── PAGINATION ────────────────────────────────────────────────
    "pagination": {
        "keywords": ["paginate", "pagination", "list", "table", "infinite scroll"],
        "packages_frontend": [],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "",
        "prompt": """
PAGINATION:
Backend:
  @bp.route('/items', methods=['GET'])
  def get_items():
      page = int(request.args.get('page', 1))
      per_page = int(request.args.get('per_page', 20))
      paginated = Item.query.order_by(Item.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
      return jsonify({'success': True, 'data': [i.to_dict() for i in paginated.items], 'total': paginated.total, 'pages': paginated.pages, 'page': page, 'has_next': paginated.has_next, 'has_prev': paginated.has_prev})

Frontend Pagination component:
  function Pagination({page, pages, onPageChange}) {
    return (
      <div className="flex items-center gap-2 justify-center mt-6">
        <button className="btn btn-ghost btn-sm" disabled={page<=1} onClick={()=>onPageChange(page-1)}>Previous</button>
        {Array.from({length:Math.min(5,pages)},(_,i)=>i+Math.max(1,page-2)).map(p=>(
          <button key={p} className={`btn btn-sm ${p===page?'btn-primary':'btn-ghost'}`} onClick={()=>onPageChange(p)}>{p}</button>
        ))}
        <button className="btn btn-ghost btn-sm" disabled={page>=pages} onClick={()=>onPageChange(page+1)}>Next</button>
      </div>
    )
  }
"""
    },

    # ── SEO ───────────────────────────────────────────────────────
    "seo": {
        "keywords": ["seo", "meta", "open graph", "title", "landing page", "marketing"],
        "packages_frontend": ["react-helmet-async"],
        "packages_backend": [],
        "env_frontend": {},
        "env_backend": {},
        "docs_url": "https://github.com/staylor/react-helmet-async",
        "prompt": """
SEO (react-helmet-async):
main.jsx: import { HelmetProvider } from 'react-helmet-async'; wrap <App/> with <HelmetProvider>

Usage in pages:
  import { Helmet } from 'react-helmet-async'
  <Helmet>
    <title>Page Title | App Name</title>
    <meta name="description" content="Page description for SEO"/>
    <meta property="og:title" content="Page Title"/>
    <meta property="og:description" content="Page description"/>
    <meta property="og:image" content="https://yourapp.com/og-image.png"/>
  </Helmet>
"""
    },
}


def detect_integrations(request: str, spec: dict) -> list:
    """Detect which integrations are needed based on project description."""
    text = (request + ' ' + str(spec)).lower()
    detected = []

    # Always include clerk if needs_auth
    if spec.get('needs_auth') or spec.get('use_clerk'):
        if 'clerk' not in detected:
            detected.append('clerk')

    # Always include stripe if needs_payments
    if spec.get('needs_payments') or spec.get('payment_type', 'none') != 'none':
        if 'stripe' not in detected:
            detected.append('stripe')

    # Always include charts for dashboard/analytics
    if spec.get('project_type') in ['saas_platform', 'dashboard']:
        if 'charts' not in detected:
            detected.append('charts')

    # Auto-detect from keywords
    for name, integration in INTEGRATIONS.items():
        if name in detected:
            continue
        for keyword in integration['keywords']:
            if keyword in text:
                detected.append(name)
                break

    return detected


def get_integration_prompt(request: str, spec: dict) -> str:
    """Build the integrations section for the generation prompt."""
    detected = detect_integrations(request, spec)
    if not detected:
        return ""

    parts = [f"\n━━━ INTEGRATIONS (auto-detected: {', '.join(detected)}) ━━━\n"]
    for name in detected:
        if name in INTEGRATIONS:
            parts.append(INTEGRATIONS[name]['prompt'])

    return '\n'.join(parts)


def get_extra_packages(request: str, spec: dict) -> dict:
    """Get all extra packages needed for detected integrations."""
    detected = detect_integrations(request, spec)
    frontend = []
    backend = []
    env_frontend = {}
    env_backend = {}

    for name in detected:
        if name in INTEGRATIONS:
            integration = INTEGRATIONS[name]
            frontend.extend(integration['packages_frontend'])
            backend.extend(integration['packages_backend'])
            env_frontend.update(integration['env_frontend'])
            env_backend.update(integration['env_backend'])

    return {
        'frontend': list(set(frontend)),
        'backend': list(set(backend)),
        'env_frontend': env_frontend,
        'env_backend': env_backend,
        'detected': detected,
    }
