import { useState, useRef, useEffect } from "react";
import "./App.css";

const API_URL = "http://localhost:8000";

export default function App() {
  const [modo, setModo] = useState("upload"); // "upload" | "camera"
  const [arquivo, setArquivo] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [apiInfo, setApiInfo] = useState(null);

  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Verifica status da API ao abrir a página
  useEffect(() => {
    fetch(`${API_URL}/`)
      .then((res) => res.json())
      .then((data) => setApiInfo(data))
      .catch(() => setApiInfo(null));
  }, []);

  // Liga/desliga a câmera conforme a aba
  useEffect(() => {
    if (modo !== "camera") return;

    let streamAtual;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" } })
      .then((stream) => {
        streamAtual = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      })
      .catch(() => setErro("Não foi possível acessar a câmera. Verifique as permissões."));

    return () => {
      if (streamAtual) {
        streamAtual.getTracks().forEach((track) => track.stop());
      }
    };
  }, [modo]);

  const selecionarArquivo = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setArquivo(file);
    setPreviewUrl(URL.createObjectURL(file));
    setResultado(null);
    setErro("");
  };

  const enviarParaAnalise = async (blobOuArquivo, nomeArquivo = "folha.jpg") => {
    setCarregando(true);
    setErro("");
    setResultado(null);

    const formData = new FormData();
    formData.append("imagem", blobOuArquivo, nomeArquivo);

    try {
      const resp = await fetch(`${API_URL}/analisar`, {
        method: "POST",
        body: formData,
      });
      const dados = await resp.json();

      if (resp.ok) {
        setResultado(dados);
      } else {
        setErro(dados.detail || "Erro ao analisar a imagem.");
      }
    } catch {
      setErro("Não foi possível conectar à API Python (verifique se api.py está rodando na porta 8000).");
    }
    setCarregando(false);
  };

  const handleAnalisarUpload = () => {
    if (!arquivo) return;
    enviarParaAnalise(arquivo, arquivo.name);
  };

  const handleCapturarEAnalisar = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    canvas.toBlob((blob) => {
      if (blob) {
        enviarParaAnalise(blob, "captura_camera.jpg");
      }
    }, "image/jpeg", 0.92);
  };

  const trocarModo = (novoModo) => {
    setModo(novoModo);
    setErro("");
    setResultado(null);
  };

  const limparUpload = () => {
    setArquivo(null);
    setPreviewUrl(null);
    setResultado(null);
    setErro("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const isSaudavel = resultado?.resultado?.toLowerCase() === "saudavel";

  return (
    <div>
      {/* Cabeçalho */}
      <header className="navbar">
        <div className="brand">
          <div className="brand-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
              <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
            </svg>
          </div>
          <div>
            <h1>AgroVision AI</h1>
            <span>Diagnóstico Fitossanitário por Visão Computacional</span>
          </div>
        </div>

        <div className="api-pill">
          <span className={`api-dot ${apiInfo ? "online" : ""}`} />
          {apiInfo ? `Modelo Online (${apiInfo.dispositivo.toUpperCase()})` : "API Offline"}
        </div>
      </header>

      <main className="container">
        {/* Abas */}
        <nav className="tabs">
          <button className={`tab-btn ${modo === "upload" ? "active" : ""}`} onClick={() => trocarModo("upload")}>
            Enviar Foto
          </button>
          <button className={`tab-btn ${modo === "camera" ? "active" : ""}`} onClick={() => trocarModo("camera")}>
            Usar Câmera
          </button>
        </nav>

        <section className="card">
          <div className="split-layout">
            {/* Coluna Esquerda: Entrada de Imagem */}
            <div>
              {modo === "upload" ? (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={selecionarArquivo}
                    style={{ display: "none" }}
                  />

                  <div className="dropzone" onClick={() => fileInputRef.current?.click()}>
                    {previewUrl ? (
                      <img src={previewUrl} alt="Pré-visualização da folha" className="preview-img" />
                    ) : (
                      <>
                        <div className="dropzone-icon">
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="17 8 12 3 7 8" />
                            <line x1="12" y1="3" x2="12" y2="15" />
                          </svg>
                        </div>
                        <h3>Clique para selecionar a foto da folha</h3>
                        <p>Formatos suportados: JPG, PNG ou WEBP (máx. 10 MB)</p>
                      </>
                    )}
                  </div>

                  <div className="actions-row">
                    <button
                      className="btn-primary"
                      onClick={handleAnalisarUpload}
                      disabled={!arquivo || carregando}
                    >
                      {carregando ? "Analisando folha..." : "Analisar Planta"}
                    </button>
                    {arquivo && (
                      <button className="btn-secondary" onClick={limparUpload} disabled={carregando}>
                        Limpar
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="camera-wrapper">
                    <video ref={videoRef} autoPlay playsInline className="camera-video" />
                    <div className="camera-badge">
                      <span className="status-dot" />
                      Câmera Ativa
                    </div>
                    <canvas ref={canvasRef} style={{ display: "none" }} />
                  </div>

                  <div className="actions-row">
                    <button
                      className="btn-primary"
                      onClick={handleCapturarEAnalisar}
                      disabled={carregando}
                    >
                      {carregando ? "Analisando captura..." : "Capturar e Analisar"}
                    </button>
                  </div>
                </>
              )}

              {erro && <div className="error-box">{erro}</div>}
            </div>

            {/* Coluna Direita: Diagnóstico */}
            <div>
              {!resultado ? (
                <div className="result-placeholder">
                  <h3 style={{ color: "var(--text-primary)", marginBottom: "8px" }}>Aguardando imagem</h3>
                  <p style={{ fontSize: "0.9rem", lineHeight: 1.5 }}>
                    Envie uma foto nítida da folha ou capture pela câmera para que a rede neural avalie a saúde da planta.
                  </p>
                </div>
              ) : (
                <div className={`result-box ${isSaudavel ? "saudavel" : "doente"}`}>
                  <div className="result-header">
                    <span className={`result-badge ${isSaudavel ? "saudavel" : "doente"}`}>
                      {isSaudavel ? "Planta Saudável" : "Sinais de Doença"}
                    </span>
                    <span className="result-time">{resultado.tempo_ms} ms</span>
                  </div>

                  <h2 className="result-title">
                    Confiança: {(resultado.confianca * 100).toFixed(1)}%
                  </h2>
                  <p className="result-message">{resultado.mensagem}</p>

                  <div className="prob-section">
                    <div className="prob-title">Detalhamento da Classificação</div>
                    {Object.entries(resultado.probabilidades).map(([classe, prob]) => {
                      const pct = (prob * 100).toFixed(1);
                      const classeCss = classe.toLowerCase() === "saudavel" ? "saudavel" : "doente";
                      return (
                        <div className="prob-item" key={classe}>
                          <div className="prob-labels">
                            <span>{classe === "saudavel" ? "Saudável" : "Doente"}</span>
                            <span>{pct}%</span>
                          </div>
                          <div className="prob-bar-bg">
                            <div className={`prob-bar-fill ${classeCss}`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}