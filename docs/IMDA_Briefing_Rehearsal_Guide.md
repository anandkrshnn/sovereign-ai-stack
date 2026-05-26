# IMDA Technical Briefing: Rehearsal & Timing Guide
**A Step-by-Step Guide for a Flawless 15-20 Minute Technical Presentation**

---

## 📅 Session Overview
*   **Target Audience:** Akriti Vij (IMDA Singapore), AI Verify Foundation Technical Evaluators.
*   **Format:** 15-20 Minute Presentation + Live Demo followed by 10-15 Minutes of Q&A.
*   **Key Objective:** Demonstrate that the Sovereign AI Stack enforces a deterministic, fail-closed security boundary using hardware and ZK proofs, directly aligning with Singapore's AI Governance policies.

---

## ⏱️ Timeline & Script Outline

### Slide 1: Title & Agenda [0:00 - 1:30]
*   **What to Say:**
    > "Good morning, Akriti and members of the IMDA and AI Verify teams. Thank you for joining us today. My name is [Your Name], and I am the lead AI Architect for the Sovereign AI Stack. 
    > 
    > Today, we are presenting a reference architecture designed to solve the single largest security vulnerability in autonomous multi-agent systems: **unverified knowledge base modifications**. Over the next 15 minutes, we will walk you through how our Prove-Transform-Verify (PTV) protocol and the Immune System Brain create a hardware-attested, fail-closed security gateway. We'll show this live in action, review how it directly fulfills the Singapore Model AI Governance Framework, and outline our integration path with the AI Verify sandbox."
*   **Emphasis Points:**
    *   Sovereign, local-first, zero cloud dependencies.
    *   Transition from "soft prompt filters" to "deterministic mathematical airlocks".
*   **Transition:**
    > "Let us start by framing the exact challenge that corporate enterprises are facing as they roll out autonomous agentic systems."

### Slide 2: The Agentic Governance Gap [1:30 - 3:30]
*   **What to Say:**
    > "Standard LLM security systems rely almost exclusively on 'soft guardrails'—such as system prompts, metaprompting, or post-generation classification APIs. While these work for basic human-in-the-loop chatbots, they fail catastrophically in multi-agent environments. 
    > 
    > If an autonomous agent is hijacked, or experiences semantic drift, it can write corrupted or malicious rules directly into a corporate vector database. Once poisoned, this data compromises the reasoning of all subsequent agents that read from it. Standard security protocols like API tokens only prove *who* the agent is—they cannot prove *how* the agent computed its decision, or whether its core instructions were compromised."
*   **Emphasis Points:**
    *   Soft guardrails are probabilistic and easy to bypass via jailbreaking.
    *   Memory poisoning propagates throughout the entire agent cluster once injected.
*   **Transition:**
    > "To address this gap, we designed a zero-trust model called the Sovereign AI Stack. Let's look at the underlying architecture."

### Slide 3: The PTV + Immune Brain Architecture [3:30 - 5:30]
*   **What to Say:**
    > "The core of our defense loop is the combination of the **Prove-Transform-Verify (PTV) protocol** and the **Immune System Brain**. 
    > 
    > Before a proposed memory event can touch the active database, it passes through the PTV Bridge. This serves as a cryptographic airlock. The agent must submit a **Groth16 Zero-Knowledge proof** showing it executed its task in compliance with corporate policies, alongside a **TPM 2.0 PCR attestation** proving it is running on secure, untampered physical hardware. 
    > 
    > Once cryptographically approved, the payload is verified semantically by our **NLI Adaptive Gate** using a local cross-encoder. Entailed updates are committed, direct contradictions are dropped, and ambiguous statements are held in a Quarantine Zone."
*   **Emphasis Points:**
    *   No external API leaks: the entire validation loop runs completely locally.
    *   Layered defense: ZK proofs secure *how* it computed; TPM secures *where* it computed; NLI secures *what* it computed.
*   **Transition:**
    > "Let us transition into the active console environment to see how this defensive structure performs under simulated attacks."

---

## 💻 Live Demo Checklist & Script [5:30 - 10:30]

### Live Demo Setup
1.  Open your terminal.
2.  Clear the console.
3.  Prepare to run the briefing mode script.

### Step 1: Secure Local Enclave Boot
*   **Command:** `python examples/demo_immune_brain.py --briefing`
*   **Show:** The clean initialization logging.
*   **Explain:** 
    > "As we boot, the system initializes our local DeBERTa cross-encoder and cryptographic modules inside our secure simulation runtime. Notice this runs instantly and fully offline with zero outbound HTTP telemetry."

### Step 2: Scenario 1 - Safe, Entailed Knowledge Insertion
*   **Show:** Scenario 1 output on the screen.
*   **Explain:** 
    > "In this scenario, a compliance agent proposes a policy: 'Employees must use 2FA for all internal systems.' The ZKP and TPM validation checks succeed. The NLI gate evaluates this payload, finds it is logically consistent with our existing memory, and accepts it. The event is permanently logged in our Layer 0 vault, updating the Merkle root."

### Step 3: Scenario 2 - Direct Contradiction Rejection (Fail-Closed)
*   **Show:** Scenario 2 output showing the red `[ REJECTED: BLOCKED FAIL-CLOSED ]` banner.
*   **Explain:** 
    > "Here, a compromised agent attempts a semantic poisoning attack by proposing that '2FA is optional'. The PTV Bridge passes origin validation, but the NLI Innate Gate identifies a direct logical contradiction. The system immediately executes a fail-closed drop, completely shielding our Verified Layer from pollution."

### Step 4: Scenario 3 - Cryptographic Bypass Attempt
*   **Show:** Scenario 3 output showing the instant rejection under 0.5 ms.
*   **Explain:** 
    > "Finally, we simulate an attacker attempting to bypass our PTV gatekeeper entirely by proposing a database change directly. The Verified Brain catches the missing validation flag and drops the packet in 0.49 milliseconds. By validating the cryptographic signature and PTV status first, we completely avoid running expensive model inference on hostile payloads."

---

## 📈 Regulatory Alignment & Roadmap [10:30 - 15:00]

### Slide 4: Singapore Framework Alignment
*   **What to Say:**
    > "Our stack directly translates Singapore's AI governance policies into executable code. We address **Transparency & Explainability** by recording explicit NLI probability matrices for every transaction. 
    > 
    > We enforce **Human-on-the-loop Accountability** through our Quarantine Zone. Any ambiguous statements are held in isolation, requiring manual approval from an administrator before merging. 
    > 
    > Finally, we ensure **Security & Resilience** through our Autoimmune Safeguard. If the rejection rate spikes above 40%, the brain dynamically scales its strictness, raising the required entailment threshold to 0.98 to insulate the database during an active threat."
*   **Emphasis Points:**
    *   Quarantine Zone is a concrete tool for human-guided operations.
    *   Autoimmune telemetry represents active cyber-defense for AI systems.

### Slide 5: Roadmap & Next Steps
*   **What to Say:**
    > "Moving forward after 15 June, our priority is setting up a cooperative sandbox evaluation. We plan to map our Layer 0 audit vault directly into the AI Verify dashboard format. 
    > 
    > In late 2026, we will be expanding our hardware attestation to support hardware-based secure enclaves like Intel SGX and TDX to guarantee security in memory during live runtime execution. We welcome collaborative testing with the IMDA evaluation team."
*   **Emphasis Points:**
    *   AI Verify sandbox integration is our immediate next milestone.
    *   Transition from software simulation to physical confidential computing.

---

## 🛠️ Rehearsal Checklist (Before the Call)
- [ ] Confirm you have `DeBERTa-v3` cached locally so the model loads in under 100ms.
- [ ] Run `python examples/demo_immune_brain.py --briefing` once to ensure no python errors or pathing issues occur.
- [ ] Have the Q&A section of `docs/IMDA_Presentation.md` open on a separate screen as a reference.
- [ ] Ensure terminal font size is large and high-contrast for remote screen sharing.
