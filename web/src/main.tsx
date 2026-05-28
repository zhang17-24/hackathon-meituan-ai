import React from "react";
import ReactDOM from "react-dom/client";
import {
  CalendarCheck,
  Camera,
  Check,
  ChevronRight,
  Clock3,
  Heart,
  ImagePlus,
  MapPin,
  MessageCircle,
  Palette,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Store,
  Wand2
} from "lucide-react";
import { BrowserRouter, NavLink, Route as AppRoute, Routes } from "react-router-dom";
import "./styles.css";

const nav = [
  { to: "/", label: "试戴", icon: Wand2 },
  { to: "/styles", label: "灵感", icon: Palette },
  { to: "/booking", label: "预约", icon: CalendarCheck },
  { to: "/service", label: "客服", icon: MessageCircle },
  { to: "/plans", label: "方案", icon: Heart }
];

const styles = [
  { name: "冰透猫眼", price: "¥168", img: "/assets/style-001.jpg", tag: "显白" },
  { name: "奶油蝴蝶结", price: "¥198", img: "/assets/style-008.jpg", tag: "约会" },
  { name: "微闪法式", price: "¥138", img: "/assets/style-enhanced-014.jpg", tag: "通勤" }
];

const runSteps = [
  ["识别手型", "已找到甲面和手部轮廓", true],
  ["保留肤色", "锁定手纹、阴影和背景", true],
  ["试戴款式", "生成 3 个自然版本", false],
  ["匹配门店", "按距离、档期和价格排序", false]
] as const;

function Shell() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark">美</div>
            <div>
              <b>美甲小助理</b>
              <span>AI 试戴 · 预约 · 售后</span>
            </div>
          </div>
          <nav className="main-nav">
            {nav.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === "/"}>
                <item.icon size={19} />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mini-card">
            <div className="mini-card-top">
              <ShieldCheck size={18} />
              <b>只改甲面</b>
            </div>
            <p>手纹、肤色、光照和背景默认保留。</p>
          </div>
        </aside>

        <main className="app-main">
          <Routes>
            <AppRoute path="/" element={<TryOnHome />} />
            <AppRoute path="/styles" element={<Styles />} />
            <AppRoute path="/booking" element={<Booking />} />
            <AppRoute path="/service" element={<Service />} />
            <AppRoute path="/plans" element={<Plans />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

function TryOnHome() {
  return (
    <div className="workspace tryon-workspace">
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow">Meituan Nail Agent</span>
          <h1>拍一下手，先试再约</h1>
          <p>看看款式上手效果，再选附近门店和空闲时间。</p>
        </div>
        <div className="quick-actions">
          <button className="primary-action">
            <ImagePlus size={20} />
            上传手图
          </button>
          <button>
            <Camera size={20} />
            直接拍照
          </button>
        </div>
      </section>

      <section className="tryon-board">
        <div className="phone-preview">
          <div className="phone-top">
            <span>当前手图</span>
            <b>自然光</b>
          </div>
          <img src="/assets/hand-006.jpg" alt="用户手部试戴预览" />
          <div className="photo-tools">
            <button>换手图</button>
            <button>调整甲型</button>
            <button>看细节</button>
          </div>
        </div>

        <div className="assistant-panel">
          <div className="assistant-head">
            <Sparkles size={22} />
            <div>
              <b>AI 正在生成试戴</b>
              <span>参考 DeerFlow 的任务流，把复杂步骤折叠成可确认进度。</span>
            </div>
          </div>
          <div className="step-list">
            {runSteps.map(([label, detail, done]) => (
              <RunStep key={label} label={label} detail={detail} done={done} />
            ))}
          </div>
          <div className="result-strip">
            <ResultThumb label="原图" src="/assets/hand-006.jpg" />
            <ResultThumb label="温柔版" src="/assets/hand-001.jpg" active />
            <ResultThumb label="闪钻版" src="/assets/style-enhanced-014.jpg" />
          </div>
          <div className="prompt-bar">
            <input placeholder="想要显白、短甲、低调一点..." />
            <button aria-label="发送偏好">
              <Send size={18} />
            </button>
          </div>
        </div>

        <aside className="style-picker">
          <div className="section-title">
            <b>推荐款式</b>
            <button>更多</button>
          </div>
          {styles.map((style) => (
            <StyleRow key={style.name} {...style} />
          ))}
        </aside>
      </section>
    </div>
  );
}

function Styles() {
  return (
    <div className="workspace">
      <PageTitle title="今日灵感" subtitle="按场景、肤色和甲型推荐" />
      <div className="search-box">
        <Search size={19} />
        <input placeholder="搜显白、短甲、猫眼、法式..." />
      </div>
      <div className="style-grid">
        {styles.concat(styles).map((style, index) => (
          <article className="style-card" key={`${style.name}-${index}`}>
            <img src={style.img} alt={style.name} />
            <div>
              <span>{style.tag}</span>
              <b>{style.name}</b>
              <p>{style.price} 起 · 附近 12 家可约</p>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function Booking() {
  const shops = [
    ["悦己美甲·万象城店", "0.8km", "今日 16:30 可约", "4.8"],
    ["Nail Lab·滨江店", "1.6km", "明日 11:00 可约", "4.9"],
    ["小鹿美甲工作室", "2.1km", "今日 19:00 可约", "4.7"]
  ];
  return (
    <div className="workspace">
      <PageTitle title="附近可约" subtitle="已按当前试戴款筛选" />
      <div className="booking-layout">
        <section className="shop-list">
          {shops.map(([name, distance, time, score]) => (
            <article className="shop-card" key={name}>
              <Store size={22} />
              <div>
                <b>{name}</b>
                <span>
                  <MapPin size={14} />
                  {distance} · {time}
                </span>
              </div>
              <strong>
                <Star size={14} />
                {score}
              </strong>
            </article>
          ))}
        </section>
        <aside className="confirm-card">
          <h2>预约单</h2>
          <p>冰透猫眼 · 温柔版</p>
          <div className="receipt-row">
            <span>预计耗时</span>
            <b>75 分钟</b>
          </div>
          <div className="receipt-row">
            <span>到店价格</span>
            <b>¥168</b>
          </div>
          <button className="wide-action">确认预约</button>
        </aside>
      </div>
    </div>
  );
}

function Service() {
  return (
    <div className="workspace service-layout">
      <section className="chat-surface">
        <PageTitle title="美甲顾问" subtitle="款式、价格、预约、售后都可以问" compact />
        <Bubble role="user" text="我的甲床偏短，猫眼会不会显手黑？" />
        <Bubble role="agent" text="建议选细闪猫眼，底色偏透粉或冷茶色。你这张手图光照偏暖，我会避开高饱和玫红。" />
        <Bubble role="user" text="如果做完有色差怎么办？" />
        <Bubble role="agent" text="下单前会给你保留试戴图和门店确认记录；到店后可按同款色号核对，售后入口也会保留在方案里。" />
        <div className="prompt-bar chat-input">
          <input placeholder="问问适合什么款、价格或售后..." />
          <button aria-label="发送">
            <Send size={18} />
          </button>
        </div>
      </section>
      <aside className="service-side">
        <b>快捷问题</b>
        {["短甲适合什么款？", "附近今天可约吗？", "做完能维持多久？", "可以换颜色吗？"].map((item) => (
          <button key={item}>{item}</button>
        ))}
      </aside>
    </div>
  );
}

function Plans() {
  return (
    <div className="workspace">
      <PageTitle title="我的方案" subtitle="试戴图、门店确认和售后记录" />
      <div className="plan-list">
        {["冰透猫眼试戴方案", "奶油蝴蝶结收藏", "通勤微闪法式"].map((plan, index) => (
          <article className="plan-card" key={plan}>
            <img src={index === 0 ? "/assets/hand-001.jpg" : styles[index % styles.length].img} alt={plan} />
            <div>
              <b>{plan}</b>
              <span>{index === 0 ? "已生成试戴 · 待预约" : "已收藏 · 可继续试戴"}</span>
            </div>
            <ChevronRight size={20} />
          </article>
        ))}
      </div>
    </div>
  );
}

function PageTitle({ title, subtitle, compact }: { title: string; subtitle: string; compact?: boolean }) {
  return (
    <header className={compact ? "page-title compact" : "page-title"}>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
  );
}

function RunStep({ label, detail, done }: { label: string; detail: string; done: boolean }) {
  return (
    <div className={done ? "run-step done" : "run-step"}>
      <span>{done ? <Check size={15} /> : <Clock3 size={15} />}</span>
      <div>
        <b>{label}</b>
        <p>{detail}</p>
      </div>
    </div>
  );
}

function ResultThumb({ label, src, active }: { label: string; src: string; active?: boolean }) {
  return (
    <button className={active ? "result-thumb active" : "result-thumb"}>
      <img src={src} alt={label} />
      <span>{label}</span>
    </button>
  );
}

function StyleRow({ name, price, img, tag }: { name: string; price: string; img: string; tag: string }) {
  return (
    <button className="style-row">
      <img src={img} alt={name} />
      <div>
        <b>{name}</b>
        <span>{tag} · {price}</span>
      </div>
      <ChevronRight size={18} />
    </button>
  );
}

function Bubble({ role, text }: { role: "user" | "agent"; text: string }) {
  return <div className={`bubble ${role}`}>{text}</div>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<Shell />);
