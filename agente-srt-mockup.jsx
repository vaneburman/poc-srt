import { useState, useEffect, useRef } from "react";

const MOCK_MESSAGES = [
  {
    role: "assistant",
    content: "¡Hola! Soy el Agente de Normativa SRT. Puedo ayudarte a:\n\n🔍 **Consultar la normativa** — Preguntame sobre campos, códigos, formatos\n📄 **Generar archivos TXT** — Creo archivos posicionales para AT y EP\n✅ **Validar archivos** — Subí un TXT y te digo si tiene errores",
    timestamp: "10:30",
  },
];

const DEMO_FLOW = [
  {
    userMsg: "¿Qué longitud tiene el campo CUIL en el AT de alta?",
    toolIndicator: { icon: "🔍", text: "Consultando normativa SRT..." },
    response:
      'El campo **CUIL del trabajador** en el archivo de Alta de AT (Resolución 3326/2014) tiene las siguientes características:\n\n- **Posición:** 2\n- **Longitud:** 11 caracteres\n- **Tipo:** Numérico (N)\n- **Padding:** Ceros a la izquierda\n- **Obligatorio:** Sí\n\nEl CUIL debe ingresarse sin guiones. Por ejemplo: `20345678901`\n\n📖 *Fuente: Res. 3326/2014, Anexo I, Campo 2*',
  },
  {
    userMsg: "Generame el AT de altas de enero 2024",
    toolIndicator: { icon: "🔨", text: "Generando archivo TXT posicional..." },
    response:
      "Archivo generado exitosamente ✅\n\n- **Archivo:** `at_alta_3reg.txt`\n- **Registros:** 3\n- **Longitud de registro:** 987 caracteres\n- **Norma:** Resolución 3326/2014\n\n¿Querés que lo valide antes de descargarlo?",
    hasDownload: true,
  },
  {
    userMsg: "Sí, validalo",
    toolIndicator: { icon: "✅", text: "Validando archivo contra esquema SRT..." },
    response:
      "El archivo es **válido** ✅\n\nSe verificaron 3 registros contra el formato de la Resolución 3326/2014:\n\n- Longitud de registros: correcta (987 chars)\n- Tipos de datos: todos válidos\n- Campos obligatorios: completos\n- Códigos de provincia: válidos\n\nEl archivo está listo para presentar ante la SRT.",
  },
];

function TypingDots() {
  return (
    <div style={{ display: "flex", gap: 4, padding: "4px 0" }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#64748b",
            animation: `bounce 1.2s ease-in-out ${i * 0.15}s infinite`,
          }}
        />
      ))}
      <style>{`@keyframes bounce { 0%,80%,100% { transform: translateY(0); } 40% { transform: translateY(-8px); } }`}</style>
    </div>
  );
}

function ToolIndicator({ icon, text }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 14px",
        background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
        border: "1px solid #334155",
        borderRadius: 8,
        fontSize: 13,
        color: "#94a3b8",
        animation: "fadeInUp 0.3s ease-out",
        margin: "4px 0",
        width: "fit-content",
      }}
    >
      <span style={{ animation: "pulse 1.5s ease-in-out infinite" }}>{icon}</span>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", letterSpacing: 0.3 }}>{text}</span>
      <TypingDots />
      <style>{`
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}

function MessageBubble({ message, isNew }) {
  const isUser = message.role === "user";
  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 16,
        animation: isNew ? "fadeInUp 0.4s ease-out" : "none",
        gap: 10,
        alignItems: "flex-start",
      }}
    >
      {!isUser && (
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 10,
            background: "linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 16,
            flexShrink: 0,
            boxShadow: "0 2px 10px rgba(244,63,94,0.3)",
          }}
        >
          🤖
        </div>
      )}
      <div
        style={{
          maxWidth: "78%",
          padding: "12px 16px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          background: isUser
            ? "linear-gradient(135deg, #e11d48 0%, #be123c 100%)"
            : "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
          color: "#f1f5f9",
          fontSize: 14,
          lineHeight: 1.65,
          border: isUser ? "none" : "1px solid #1e293b",
          boxShadow: isUser
            ? "0 2px 12px rgba(225,29,60,0.25)"
            : "0 2px 8px rgba(0,0,0,0.2)",
        }}
      >
        <div
          dangerouslySetInnerHTML={{
            __html: message.content
              .replace(/\*\*(.*?)\*\*/g, "<strong style='color:#f9fafb'>$1</strong>")
              .replace(/`(.*?)`/g, "<code style='background:#334155;padding:1px 5px;border-radius:4px;font-family:JetBrains Mono,monospace;font-size:12px;color:#fbbf24'>$1</code>")
              .replace(/\n/g, "<br/>")
              .replace(/\*(.*?)\*/g, "<em style='color:#94a3b8'>$1</em>"),
          }}
        />
      </div>
      {isUser && (
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 10,
            background: "linear-gradient(135deg, #475569 0%, #334155 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 15,
            flexShrink: 0,
          }}
        >
          👤
        </div>
      )}
    </div>
  );
}

function DownloadButton() {
  return (
    <button
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "10px 20px",
        background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
        border: "none",
        borderRadius: 10,
        color: "#f0fdf4",
        fontSize: 13,
        fontWeight: 600,
        cursor: "pointer",
        margin: "8px 0 8px 44px",
        boxShadow: "0 2px 10px rgba(5,150,105,0.3)",
        fontFamily: "'DM Sans', sans-serif",
        animation: "fadeInUp 0.3s ease-out",
      }}
    >
      📥 Descargar at_alta_3reg.txt
    </button>
  );
}

export default function AgenteSRTMockup() {
  const [messages, setMessages] = useState(MOCK_MESSAGES);
  const [inputValue, setInputValue] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [demoStep, setDemoStep] = useState(0);
  const [showTool, setShowTool] = useState(null);
  const [showDownload, setShowDownload] = useState(false);
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, showTool]);

  const simulateResponse = (step) => {
    const flow = DEMO_FLOW[step];
    if (!flow) return;

    setIsProcessing(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: flow.userMsg, timestamp: "10:3" + (1 + step) },
    ]);

    setTimeout(() => {
      setShowTool(flow.toolIndicator);
    }, 600);

    setTimeout(() => {
      setShowTool(null);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: flow.response, timestamp: "10:3" + (1 + step), isNew: true },
      ]);
      if (flow.hasDownload) setShowDownload(true);
      setIsProcessing(false);
      setDemoStep(step + 1);
    }, 2400);
  };

  const handleSend = () => {
    if (isProcessing || demoStep >= DEMO_FLOW.length) return;
    setInputValue("");
    setShowDownload(false);
    simulateResponse(demoStep);
  };

  const quickActions = [
    { label: "📋 Consultar normativa", prompt: "¿Qué longitud tiene el campo CUIL?" },
    { label: "📄 Generar AT Alta", prompt: "Generame el AT de altas de enero 2024" },
    { label: "✅ Validar archivo", prompt: "Validá el último archivo generado" },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#030712",
        fontFamily: "'DM Sans', sans-serif",
        display: "flex",
        color: "#f1f5f9",
      }}
    >
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet" />

      {/* Sidebar */}
      <div
        style={{
          width: 280,
          background: "linear-gradient(180deg, #0f172a 0%, #020617 100%)",
          borderRight: "1px solid #1e293b",
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 24,
          flexShrink: 0,
        }}
      >
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: "linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              boxShadow: "0 4px 15px rgba(244,63,94,0.35)",
            }}
          >
            📋
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: -0.3 }}>Agente SRT</div>
            <div style={{ fontSize: 11, color: "#64748b", fontWeight: 500 }}>PoC v2.0</div>
          </div>
        </div>

        {/* Generate Section */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 12 }}>
            ⚡ Generar Archivo
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <select
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 13,
                  outline: "none",
                }}
              >
                <option>AT</option>
                <option>EP</option>
              </select>
              <select
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 13,
                  outline: "none",
                }}
              >
                <option>Alta</option>
                <option>Baja</option>
              </select>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="date"
                defaultValue="2024-01-01"
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 12,
                  outline: "none",
                }}
              />
              <input
                type="date"
                defaultValue="2024-01-31"
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 12,
                  outline: "none",
                }}
              />
            </div>
            <button
              style={{
                padding: "10px 16px",
                background: "linear-gradient(135deg, #e11d48 0%, #be123c 100%)",
                border: "none",
                borderRadius: 8,
                color: "white",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "'DM Sans', sans-serif",
                boxShadow: "0 2px 10px rgba(225,29,60,0.3)",
              }}
            >
              🔨 Generar TXT
            </button>
          </div>
        </div>

        {/* Validate Section */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 12 }}>
            ✅ Validar Archivo
          </div>
          <div
            style={{
              border: "2px dashed #334155",
              borderRadius: 10,
              padding: "20px 16px",
              textAlign: "center",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "#f43f5e";
              e.currentTarget.style.background = "rgba(244,63,94,0.05)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#334155";
              e.currentTarget.style.background = "transparent";
            }}
          >
            <div style={{ fontSize: 24, marginBottom: 6 }}>📂</div>
            <div style={{ fontSize: 12, color: "#94a3b8" }}>
              Arrastrá tu archivo .TXT
            </div>
            <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>.txt .at .ep</div>
          </div>
        </div>

        {/* Stats */}
        <div style={{ marginTop: "auto", padding: "14px 0", borderTop: "1px solid #1e293b" }}>
          <div style={{ fontSize: 11, color: "#475569", marginBottom: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>
            Esquemas cargados
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {["AT Alta", "AT Baja", "EP Alta", "EP Baja"].map((s) => (
              <span
                key={s}
                style={{
                  padding: "4px 10px",
                  background: "#1e293b",
                  borderRadius: 6,
                  fontSize: 11,
                  color: "#94a3b8",
                  border: "1px solid #334155",
                }}
              >
                {s}
              </span>
            ))}
          </div>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 12 }}>
            📚 200 chunks normativos • FAISS index activo
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <div
          style={{
            padding: "16px 28px",
            borderBottom: "1px solid #1e293b",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(15,23,42,0.6)",
            backdropFilter: "blur(12px)",
          }}
        >
          <div>
            <span style={{ fontSize: 15, fontWeight: 600 }}>Agente IA — Normativa SRT</span>
            <span
              style={{
                marginLeft: 12,
                padding: "3px 10px",
                background: "rgba(34,197,94,0.15)",
                color: "#4ade80",
                borderRadius: 20,
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              ● Conectado — Gemini 2.0 Flash
            </span>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <span style={{ padding: "4px 10px", background: "#1e293b", borderRadius: 6, fontSize: 11, color: "#94a3b8" }}>
              Res. 3326/2014
            </span>
            <span style={{ padding: "4px 10px", background: "#1e293b", borderRadius: 6, fontSize: 11, color: "#94a3b8" }}>
              Res. 3327/2014
            </span>
          </div>
        </div>

        {/* Messages */}
        <div
          ref={chatRef}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "24px 28px",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} isNew={msg.isNew} />
          ))}
          {showTool && <ToolIndicator icon={showTool.icon} text={showTool.text} />}
          {showDownload && <DownloadButton />}
        </div>

        {/* Quick Actions */}
        {demoStep < DEMO_FLOW.length && (
          <div style={{ padding: "0 28px 8px", display: "flex", gap: 8, flexWrap: "wrap" }}>
            {quickActions.map((qa, i) => (
              <button
                key={i}
                onClick={() => {
                  if (!isProcessing) {
                    setInputValue(qa.prompt);
                  }
                }}
                style={{
                  padding: "6px 14px",
                  background: "transparent",
                  border: "1px solid #334155",
                  borderRadius: 20,
                  color: "#94a3b8",
                  fontSize: 12,
                  cursor: "pointer",
                  fontFamily: "'DM Sans', sans-serif",
                  transition: "all 0.2s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "#f43f5e";
                  e.currentTarget.style.color = "#f1f5f9";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "#334155";
                  e.currentTarget.style.color = "#94a3b8";
                }}
              >
                {qa.label}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div
          style={{
            padding: "16px 28px 20px",
            borderTop: "1px solid #1e293b",
            background: "rgba(15,23,42,0.6)",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              background: "#1e293b",
              borderRadius: 14,
              padding: "6px 6px 6px 18px",
              border: "1px solid #334155",
            }}
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Preguntá sobre normativa SRT, pedí generar o validar archivos..."
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#e2e8f0",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
              }}
            />
            <button
              onClick={handleSend}
              disabled={isProcessing}
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: isProcessing
                  ? "#334155"
                  : "linear-gradient(135deg, #e11d48 0%, #be123c 100%)",
                border: "none",
                color: "white",
                fontSize: 18,
                cursor: isProcessing ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: isProcessing ? "none" : "0 2px 10px rgba(225,29,60,0.3)",
                transition: "all 0.2s",
              }}
            >
              ↑
            </button>
          </div>
          <div style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: "#334155" }}>
            Motor determinístico + RAG sobre Res. 3326 y 3327 • Costo: $0.00
          </div>
        </div>
      </div>
    </div>
  );
}
