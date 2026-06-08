const { useState, useEffect } = React;

const C = {
    bg: "#f5f4f1",
    surf: "#ffffff",
    bdr: "#e5e2dc",
    bdrMed: "#ccc9c2",
    txt: "#1c1b19",
    muted: "#72706c",
    light: "#a09e9a",
    blue: "#1d6fb8",
    blueBg: "#eaf3fc",
    blueText: "#0d4d87",
    green: "#2d7d3a",
    greenBg: "#eaf5ec",
    greenText: "#1a5224",
    amber: "#b36a0f",
    amberBg: "#fef4e6",
    amberText: "#7a4500",
    red: "#c0392b",
    redBg: "#fdf0ee",
    redText: "#8b1a10",
    grayBg: "#f0ede8",
    grayText: "#3a3835",
};

function Badge({ type, children }) {
    const m = {
        po: { bg: C.blueBg, color: C.blueText },
        dc: { bg: C.greenBg, color: C.greenText },
        inv: { bg: C.amberBg, color: C.amberText },
        matched: { bg: C.greenBg, color: C.greenText },
        mismatch: { bg: C.redBg, color: C.redText },
        approved: { bg: C.greenBg, color: C.greenText },
        rejected: { bg: C.redBg, color: C.redText },
        query: { bg: C.amberBg, color: C.amberText },
        pending: { bg: C.grayBg, color: C.grayText },
        warn: { bg: C.amberBg, color: C.amberText },
    };
    const s = m[type] || m.pending;

    return React.createElement(
        "span",
        {
            style: {
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                background: s.bg,
                color: s.color,
                fontSize: "11px",
                fontWeight: 700,
                padding: "3px 9px",
                borderRadius: "5px",
            },
        },
        children
    );
}

function Btn({ onClick, variant = "def", children, disabled }) {
    const vs = {
        def: { bg: C.surf, color: C.txt, bdr: C.bdrMed },
        primary: { bg: C.blue, color: "#fff", bdr: C.blue },
        green: { bg: C.greenBg, color: C.greenText, bdr: "#aed6b3" },
        red: { bg: C.redBg, color: C.redText, bdr: "#f0b0a8" },
        amber: { bg: C.amberBg, color: C.amberText, bdr: "#f0c878" },
    };
    const v = vs[variant];

    return React.createElement(
        "button",
        {
            onClick,
            disabled,
            style: {
                flex: 1,
                padding: "7px 8px",
                fontSize: "12px",
                fontWeight: 600,
                border: `1px solid ${v.bdr}`,
                borderRadius: "7px",
                background: v.bg,
                color: v.color,
                cursor: disabled ? "default" : "pointer",
                opacity: disabled ? 0.5 : 1,
            },
        },
        children
    );
}

function ProgressBar({ pct }) {
    return React.createElement(
        "div",
        {
            style: {
                height: "3px",
                background: C.bdr,
                borderRadius: "2px",
                overflow: "hidden",
                marginBottom: "6px",
            },
        },
        React.createElement("div", {
            style: {
                height: "100%",
                width: `${pct}%`,
                background: C.blue,
                borderRadius: "2px",
                transition: "width 0.5s ease",
            },
        })
    );
}

const DOC_ICONS = { "Purchase Order": "📋", "Delivery Challan": "🚚", Invoice: "🧾" };
const DOC_BADGE = { "Purchase Order": "po", "Delivery Challan": "dc", Invoice: "inv" };

function DocCard({ type, name }) {
    return React.createElement(
        "div",
        {
            style: {
                border: `1px solid ${C.bdr}`,
                borderRadius: "9px",
                padding: "12px 8px",
                background: C.surf,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "6px",
                textAlign: "center",
            },
        },
        React.createElement("span", { style: { fontSize: "22px" } }, DOC_ICONS[type]),
        React.createElement(Badge, { type: DOC_BADGE[type] }, type),
        React.createElement("span", { style: { fontSize: "11px", color: C.muted } }, name)
    );
}

const NODES = [
    { id: "upload", label: "upload_documents" },
    { id: "classify", label: "classify_documents" },
    { id: "ocr", label: "ocr_validation" },
    { id: "human_ocr", label: "human_review" },
    { id: "extract", label: "data_extraction" },
    { id: "dc", label: "dc_processing" },
    { id: "match", label: "three_way_matching" },
    { id: "approval", label: "human_approval" },
    { id: "payment", label: "trigger_payment" },
];

function TraceDot({ status }) {
    const cfg = {
        waiting: { bg: C.bg, bdr: C.bdrMed, sym: "", c: C.light },
        active: { bg: C.blueBg, bdr: C.blue, sym: "◌", c: C.blue },
        done: { bg: C.greenBg, bdr: "#aed6b3", sym: "✓", c: C.greenText },
        warn: { bg: C.amberBg, bdr: "#f0c878", sym: "!", c: C.amberText },
        error: { bg: C.redBg, bdr: "#f0b0a8", sym: "✕", c: C.redText },
        hitl: { bg: C.amberBg, bdr: "#f0c878", sym: "⏸", c: C.amberText },
    };
    const s = cfg[status] || cfg.waiting;

    return React.createElement(
        "div",
        {
            style: {
                width: "18px",
                height: "18px",
                borderRadius: "50%",
                flexShrink: 0,
                background: s.bg,
                border: `1.5px solid ${s.bdr}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "9px",
                fontWeight: 800,
                color: s.c,
                marginTop: "2px",
            },
        },
        s.sym
    );
}

function TraceItem({ label, status, detail, time, isLast }) {
    return React.createElement(
        "div",
        {
            style: {
                display: "flex",
                gap: "8px",
                paddingBottom: isLast ? 0 : "10px",
                position: "relative",
            },
        },
        !isLast &&
        React.createElement("div", {
            style: {
                position: "absolute",
                left: "8px",
                top: "20px",
                bottom: 0,
                width: "1px",
                background: C.bdr,
            },
        }),
        React.createElement(TraceDot, { status }),
        React.createElement(
            "div",
            { style: { flex: 1, minWidth: 0 } },
            React.createElement(
                "div",
                { style: { fontSize: "11px", fontWeight: 600, color: C.txt, lineHeight: 1.3 } },
                label
            ),
            detail &&
            React.createElement(
                "div",
                { style: { fontSize: "10px", color: C.muted, marginTop: "1px" } },
                detail
            ),
            time &&
            React.createElement(
                "div",
                { style: { fontSize: "10px", color: C.light, marginTop: "1px" } },
                time
            )
        )
    );
}

function HitlBanner({ title, note, children }) {
    return React.createElement(
        "div",
        {
            style: {
                border: `1px solid #e8d48a`,
                borderRadius: "9px",
                background: C.amberBg,
                padding: "12px 14px",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
            },
        },
        React.createElement(
            "div",
            { style: { display: "flex", gap: "8px", alignItems: "flex-start" } },
            React.createElement("span", { style: { fontSize: "16px" } }, "⏸"),
            React.createElement(
                "div",
                null,
                React.createElement(
                    "div",
                    { style: { fontWeight: 700, fontSize: "12px", color: C.amberText } },
                    title
                ),
                note &&
                React.createElement(
                    "div",
                    {
                        style: {
                            fontSize: "11px",
                            color: C.amberText,
                            opacity: 0.8,
                            marginTop: "2px",
                        },
                    },
                    note
                )
            )
        ),
        React.createElement("div", { style: { display: "flex", gap: "7px" } }, children)
    );
}

function DataTable({ rows }) {
    return React.createElement(
        "table",
        { style: { width: "100%", borderCollapse: "collapse", fontSize: "12px" } },
        React.createElement(
            "tbody",
            null,
            rows.map(([k, v], i) =>
                React.createElement(
                    "tr",
                    {
                        key: i,
                        style: { borderBottom: i < rows.length - 1 ? `1px solid ${C.bdr}` : "none" },
                    },
                    React.createElement(
                        "td",
                        { style: { padding: "5px 0", color: C.muted, width: "45%" } },
                        k
                    ),
                    React.createElement("td", { style: { padding: "5px 0", fontWeight: 600 } }, v)
                )
            )
        )
    );
}

function MetricCard({ label, value }) {
    return React.createElement(
        "div",
        { style: { background: C.bg, borderRadius: "8px", padding: "11px 13px" } },
        React.createElement(
            "div",
            { style: { fontSize: "11px", color: C.muted, marginBottom: "6px" } },
            label
        ),
        React.createElement("div", null, value)
    );
}

const sLabel = {
    fontSize: "10px",
    fontWeight: 700,
    letterSpacing: "0.08em",
    color: C.light,
    textTransform: "uppercase",
    marginBottom: "10px",
};

const card = {
    background: C.surf,
    border: `1px solid ${C.bdr}`,
    borderRadius: "10px",
    padding: "14px 16px",
};

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

function App() {
    const [phase, setPhase] = useState("idle");
    const [pct, setPct] = useState(0);

    const initTrace = Object.fromEntries(
        NODES.map((n) => [n.id, { status: "waiting", detail: null, time: null }])
    );

    const [trace, setTrace] = useState(initTrace);
    const [vis, setVis] = useState({
        classify: false,
        extract: false,
        result: false,
        hitlOCR: false,
        hitlApproval: false,
        payment: false,
    });

    const [matchSt, setMatchSt] = useState(null);
    const [approvSt, setApprovSt] = useState(null);
    const [findings, setFindings] = useState([]);
    const [extraNodes, setExtraNodes] = useState([]);

    const setT = (id, status, detail, time) =>
        setTrace((p) => ({
            ...p,
            [id]: { status, detail: detail ?? p[id].detail, time: time ?? p[id].time },
        }));

    const show = (k) => setVis((p) => ({ ...p, [k]: true }));
    const hide = (k) => setVis((p) => ({ ...p, [k]: false }));
    const [frm, setFrm] = useState({ po: "", amt: "5?000" });
    const [ext, setExt] = useState({ 
        po: "PO-123", 
        inv: "INV-456", 
        ven: "ABC Ltd", 
        amt: "₹50,000", 
        dc: "2", 
        qty: "15" 
    });

    async function startWorkflow() {
        if (phase !== "uploaded") return;

        setPhase("running");
        setT("upload", "active", "processing...");
        setPct(5);

        await delay(600);
        setT("upload", "done", "3 docs received", "0.1s");
        setPct(13);

        await delay(300);
        setT("classify", "active", "classifying...");

        await delay(700);
        setT("classify", "done", "PO / DC / Invoice", "0.4s");
        setPct(24);
        show("classify");

        await delay(400);
        setT("ocr", "active", "running OCR engine...");

        await delay(900);
        setT("ocr", "warn", "conf 0.65 — below threshold", "0.6s");
        setPct(34);

        await delay(300);
        setT("human_ocr", "hitl", "awaiting reviewer");
        show("hitlOCR");
        setPhase("hitl_ocr");
    }

    async function resolveOCR(d) {
        if (phase !== "hitl_ocr") return;

        setPhase("running");
        hide("hitlOCR");
        setT("human_ocr", "done", d === "satisfactory" ? "accepted w/ corrections" : "re-upload requested", "manual");
        setPct(44);

        await delay(400);
        setT("extract", "active", "extracting fields...");

        await delay(700);
        
        if (d === "satisfactory") {
            const npo = frm.po || "PO-123";
            const nam = frm.amt !== "5?000" ? `₹${frm.amt}` : "₹50,000";
            
            setExt(p => ({ ...p, po: npo, amt: nam }));
            setT("extract", "done", `${npo} · INV-456 · ${nam}`, "0.5s");
        } else {
            setT("extract", "done", "PO-123 · INV-456 · ₹50,000", "0.5s");
        }
        
        setPct(56);
        show("extract");

        await delay(400);
        setT("dc", "active", "parsing delivery challans...");
    }

    async function resolveApproval(d) {
        if (phase !== "hitl_approval") return;

        setPhase("running");
        hide("hitlApproval");

        if (d === "approve") {
            setT("approval", "done", "approved", "manual");
            setApprovSt("approved");
            setPct(88);

            await delay(500);
            setT("payment", "active", "triggering ERP...");

            await delay(700);
            setT("payment", "done", "₹50,000 queued", "0.4s");
            setPct(100);
            show("payment");
        } else if (d === "reject") {
            setT("approval", "error", "rejected", "manual");
            setApprovSt("rejected");
            setFindings([
                "Invoice total does not match agreed PO rate after GST adjustment",
                "Delivery date on challan precedes PO issue date",
            ]);
            setPct(100);
        } else {
            setT("approval", "warn", "supplier query raised", "manual");
            setApprovSt("query");
            setPct(84);
            setExtraNodes((p) => [
                ...p,
                { label: "supplier_loop", detail: "query sent → resolved", status: "done" },
            ]);

            await delay(1000);
            setExtraNodes((p) => [
                ...p,
                { label: "trigger_payment", detail: "₹50,000 queued", status: "done" },
            ]);
            setPct(100);
            show("payment");
        }

        setPhase("done");
    }

    const allNodes = [...NODES, ...extraNodes.map((n, i) => ({ id: `ex_${i}`, _e: n }))];

    return React.createElement(
        "div",
        {
            style: {
                display: "flex",
                height: "640px",
                fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
                background: C.bg,
                borderRadius: "14px",
                border: `1px solid ${C.bdr}`,
                overflow: "hidden",
                fontSize: "13px",
                color: C.txt,
            },
        },
        React.createElement(
            "div",
            {
                style: {
                    flex: 1,
                    minWidth: 0,
                    overflowY: "auto",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "13px",
                },
            },
            React.createElement(ProgressBar, { pct }),

            React.createElement(
                "div",
                { style: card },
                React.createElement("div", { style: sLabel }, "document upload"),
                React.createElement(
                    "div",
                    {
                        onClick: () => {
                            if (phase === "idle") setPhase("uploaded");
                        },
                        style: {
                            border: `1.5px dashed ${phase !== "idle" ? C.bdrMed : C.blue}`,
                            borderRadius: "9px",
                            padding: "20px",
                            textAlign: "center",
                            cursor: phase === "idle" ? "pointer" : "default",
                            background: phase !== "idle" ? C.bg : C.blueBg,
                            transition: "all 0.2s",
                        },
                    },
                    React.createElement(
                        "div",
                        { style: { fontSize: "28px", marginBottom: "6px" } },
                        phase === "idle" ? "☁" : "✅"
                    ),
                    React.createElement(
                        "div",
                        {
                            style: {
                                fontSize: "13px",
                                fontWeight: 600,
                                color: phase === "idle" ? C.blue : C.greenText,
                            },
                        },
                        phase === "idle"
                            ? "Click to upload documents"
                            : "po.pdf, dc.pdf, invoice.pdf uploaded"
                    ),
                    React.createElement(
                        "div",
                        { style: { fontSize: "11px", color: C.muted, marginTop: "3px" } },
                        phase === "idle" ? "Supports PDF, PNG, JPEG" : "3 files ready to process"
                    )
                ),
                phase !== "idle" &&
                React.createElement(
                    "div",
                    { style: { display: "flex", gap: "7px", marginTop: "10px", flexWrap: "wrap" } },
                    [
                        ["po.pdf", "po"],
                        ["dc.pdf", "dc"],
                        ["invoice.pdf", "inv"],
                    ].map(([n, t]) =>
                        React.createElement(Badge, { key: n, type: t }, "📄 " + n)
                    )
                )
            ),

            phase === "uploaded" &&
            React.createElement(
                "button",
                {
                    onClick: startWorkflow,
                    style: {
                        width: "100%",
                        padding: "10px",
                        background: C.blue,
                        color: "#fff",
                        border: "none",
                        borderRadius: "8px",
                        fontSize: "13px",
                        fontWeight: 700,
                        cursor: "pointer",
                        letterSpacing: "0.02em",
                    },
                },
                "▶  Run workflow"
            ),

            vis.classify &&
            React.createElement(
                "div",
                { style: card },
                React.createElement("div", { style: sLabel }, "classified documents"),
                React.createElement(
                    "div",
                    { style: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" } },
                    ["Purchase Order", "Delivery Challan", "Invoice"].map((t, i) =>
                        React.createElement(DocCard, {
                            key: t,
                            type: t,
                            name: ["po.pdf", "dc.pdf", "invoice.pdf"][i],
                        })
                    )
                )
            ),

            vis.hitlOCR &&
            React.createElement(
                HitlBanner,
                {
                    title: "OCR confidence below threshold",
                    note: "Confidence 65% · threshold 75% · Edit fields before approving",
                },
                React.createElement(
                    "div",
                    { style: { display: "flex", flexDirection: "column", gap: "8px", width: "100%" } },
                    React.createElement(
                        "div",
                        { style: { display: "flex", gap: "10px" } },
                        React.createElement("input", {
                            value: frm.po,
                            onChange: (e) => setFrm({ ...frm, po: e.target.value }),
                            placeholder: "PO Number (e.g. PO-123)",
                            style: { padding: "6px 8px", borderRadius: "5px", border: `1px solid ${C.bdrMed}`, fontSize: "12px", flex: 1, outline: "none" }
                        }),
                        React.createElement("input", {
                            value: frm.amt,
                            onChange: (e) => setFrm({ ...frm, amt: e.target.value }),
                            placeholder: "Amount",
                            style: { padding: "6px 8px", borderRadius: "5px", border: `1px solid ${C.bdrMed}`, fontSize: "12px", flex: 1, outline: "none" }
                        })
                    ),
                    React.createElement(
                        "div",
                        { style: { display: "flex", gap: "7px" } },
                        React.createElement(
                            Btn,
                            { variant: "green", onClick: () => resolveOCR("satisfactory") },
                            "✓ Satisfactory"
                        ),
                        React.createElement(
                            Btn,
                            { variant: "red", onClick: () => resolveOCR("not_satisfactory") },
                            "↺ Request re-upload"
                        )
                    )
                )
            ),

            vis.extract &&
            React.createElement(
                "div",
                { style: card },
                React.createElement("div", { style: sLabel }, "extracted data"),
                React.createElement(DataTable, {
                    rows: [
                        ["PO Number", ext.po],
                        ["Invoice Number", ext.inv],
                        ["Vendor", ext.ven],
                        ["Amount", ext.amt],
                        ["DC Count", ext.dc],
                        ["Total Quantity", ext.qty],
                    ],
                })
            ),

            vis.result &&
            React.createElement(
                "div",
                { style: card },
                React.createElement("div", { style: sLabel }, "results"),
                React.createElement(
                    "div",
                    {
                        style: {
                            display: "grid",
                            gridTemplateColumns: "1fr 1fr",
                            gap: "10px",
                            marginBottom: findings.length ? "14px" : 0,
                        },
                    },
                    React.createElement(MetricCard, {
                        label: "Match status",
                        value:
                            matchSt === "matched"
                                ? React.createElement(Badge, { type: "matched" }, "✓ Matched")
                                : matchSt === "mismatch"
                                    ? React.createElement(Badge, { type: "mismatch" }, "✕ Mismatch")
                                    : "—",
                    }),
                    React.createElement(MetricCard, {
                        label: "Approval status",
                        value:
                            approvSt === "approved"
                                ? React.createElement(Badge, { type: "approved" }, "✓ Approved")
                                : approvSt === "rejected"
                                    ? React.createElement(Badge, { type: "rejected" }, "✕ Rejected")
                                    : approvSt === "query"
                                        ? React.createElement(Badge, { type: "query" }, "→ Query sent")
                                        : React.createElement(Badge, { type: "pending" }, "⏳ Pending"),
                    })
                ),
                findings.length > 0 &&
                React.createElement(
                    "div",
                    null,
                    React.createElement(
                        "div",
                        { style: { ...sLabel, marginTop: "10px" } },
                        "findings"
                    ),
                    React.createElement(
                        "div",
                        { style: { display: "flex", flexDirection: "column", gap: "6px" } },
                        findings.map((f, i) =>
                            React.createElement(
                                "div",
                                {
                                    key: i,
                                    style: {
                                        display: "flex",
                                        gap: "8px",
                                        alignItems: "flex-start",
                                        background: C.redBg,
                                        border: "1px solid #f0b0a8",
                                        borderRadius: "7px",
                                        padding: "8px 10px",
                                        fontSize: "12px",
                                        color: C.redText,
                                    },
                                },
                                React.createElement("span", { style: { flexShrink: 0 } }, "⚠"),
                                React.createElement("span", null, f)
                            )
                        )
                    )
                )
            ),

            vis.hitlApproval &&
            React.createElement(
                HitlBanner,
                {
                    title: "Awaiting final approval",
                    note: "Review extracted data and match results before proceeding",
                },
                React.createElement(
                    Btn,
                    { variant: "green", onClick: () => resolveApproval("approve") },
                    "✓ Approve"
                ),
                React.createElement(
                    Btn,
                    { variant: "red", onClick: () => resolveApproval("reject") },
                    "✕ Reject"
                ),
                React.createElement(
                    Btn,
                    { variant: "amber", onClick: () => resolveApproval("raise_query") },
                    "→ Raise query"
                )
            ),

            vis.payment &&
            React.createElement(
                "div",
                {
                    style: {
                        background: C.greenBg,
                        border: "1px solid #aed6b3",
                        borderRadius: "10px",
                        padding: "14px 16px",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                    },
                },
                React.createElement(
                    "div",
                    {
                        style: {
                            width: "38px",
                            height: "38px",
                            borderRadius: "50%",
                            background: C.greenText,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "18px",
                            color: "#fff",
                            flexShrink: 0,
                        },
                    },
                    "✓"
                ),
                React.createElement(
                    "div",
                    null,
                    React.createElement(
                        "div",
                        { style: { fontWeight: 700, color: C.greenText } },
                        "Payment triggered"
                    ),
                    React.createElement(
                        "div",
                        { style: { fontSize: "12px", color: C.green, marginTop: "2px" } },
                        "Invoice INV-456 · ₹50,000 · Vendor ABC Ltd"
                    )
                )
            )
        ),

        React.createElement(
            "div",
            {
                style: {
                    width: "196px",
                    flexShrink: 0,
                    borderLeft: `1px solid ${C.bdr}`,
                    background: C.surf,
                    padding: "16px 14px",
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                },
            },
            React.createElement(
                "div",
                {
                    style: {
                        fontSize: "11px",
                        fontWeight: 700,
                        letterSpacing: "0.07em",
                        color: C.light,
                        textTransform: "uppercase",
                        marginBottom: "14px",
                        paddingBottom: "10px",
                        borderBottom: `1px solid ${C.bdr}`,
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                    },
                },
                React.createElement("span", { style: { fontSize: "13px" } }, "◈"),
                " Agent trace"
            ),
            NODES.map((node, i) => {
                const t = trace[node.id];
                const isLast = i === NODES.length - 1 && extraNodes.length === 0;
                return React.createElement(TraceItem, {
                    key: node.id,
                    label: node.label,
                    status: t.status,
                    detail: t.detail,
                    time: t.time,
                    isLast,
                });
            }),
            extraNodes.map((n, i) =>
                React.createElement(TraceItem, {
                    key: "ex" + i,
                    label: n.label,
                    status: n.status,
                    detail: n.detail,
                    time: null,
                    isLast: i === extraNodes.length - 1,
                })
            )
        )
    );
}

ReactDOM.createRoot(document.getElementById("root")).render(
    React.createElement(App)
);
