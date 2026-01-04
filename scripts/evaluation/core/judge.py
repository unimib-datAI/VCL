import json
import concurrent.futures
from openai import OpenAI
from typing import List, Dict

client = OpenAI()

class GPTJudge:
    CHUNK_SIZE = 800

    def __init__(self, model: str, project_root: str):
        self.MODEL = model
        self.project_root = project_root
        self.documents = []

    def _execute_evaluation(self, prompt: str, system_message: str = "Sei un auditor legale esperto in analisi di conformità e logica formale.") -> Dict:
        """Esegue la chiamata a GPT con vincolo JSON."""
        try:
            response = client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"score": 0.0, "motivation": f"Errore critico API: {str(e)}"}

    # ---------------------------------------------------------
    # METRICHE OTTIMIZZATE CON LOGICA LEGALE RIGOROSA
    # ---------------------------------------------------------

    def evaluate_precision(self, answer: str, ground_truth: str) -> Dict:
        """Precision (Veracità): Valuta l'assenza di falsità dichiarative."""
        claims = self.split_claims(answer)
        if not claims: return {"total_score": 0.0, "claims_analysis": []}
        
        def eval_claim(c):
            prompt = f"""
            ANALISI DI PRECISIONE FATTUALE (Legale)
            CONTESTO (Ground Truth): {ground_truth}
            CLAIM DA VALIDARE: "{c}"

            DEFINIZIONE RIGOROSA: La Precision misura l'assenza di errori materiali o contraddizioni rispetto alla Ground Truth (GT).
            - NON penalizzare l'incompletezza (omissione di dettagli presenti nella GT).
            - NON penalizzare la mancanza di citazioni.
            - Penalizza solo l'affermazione di fatti non veri o contrari alla GT.

            ESEMPIO:
            - GT: "Il contratto può essere risolto con preavviso di 30 giorni per giusta causa."
            - CLAIM: "Il contratto è risolvibile." -> SCORE 1.0 (Vero, anche se incompleto).
            - CLAIM: "Il preavviso è di 15 giorni." -> SCORE 0.0 (Falso/Contraddittorio).

            SCALA DI VALUTAZIONE:
            1.0: Pienamente corretto o logicamente derivabile per implicazione diretta.
            0.75: Corretto, ma utilizza una terminologia giuridica leggermente imprecisa che non altera il senso.
            0.5: Parzialmente corretto, ma contiene una sfumatura che potrebbe indurre in errore minore.
            0.25: Gravemente impreciso, pur mantenendo un barlume di verità.
            0.0: Falso, allucinato o in aperta contraddizione con la GT.

            Rispondi in JSON: {{"score": float, "motivation": "Analisi tecnica della veridicità"}}
            """
            return {"claim": c, **self._execute_evaluation(prompt)}

        with concurrent.futures.ThreadPoolExecutor() as executor:
            analysis = list(executor.map(eval_claim, claims))
        
        total = sum(item["score"] for item in analysis) / len(claims)
        return {"total_score": total, "claims_analysis": analysis}

    def evaluate_recall(self, answer: str, ground_truth: str) -> Dict:
        """Recall (Esaustività Rispetto alla Fonte): Valuta la copertura dei requisiti."""
        gt_claims = self.split_claims(ground_truth)
        if not gt_claims: return {"total_score": 0.0, "claims_analysis": []}
        
        def eval_recall_item(gc):
            prompt = f"""
            ANALISI DI RECALL (Copertura Requisiti)
            RISPOSTA FORNITA: {answer}
            REQUISITO GT DA TROVARE: "{gc}"

            DEFINIZIONE RIGOROSA: La Recall misura se ogni punto fondamentale della GT è stato trasposto nella risposta.
            - NON penalizzare la presenza di informazioni extra (non pertinenti alla GT).
            - NON valutare la correttezza delle informazioni extra.
            - Valuta solo se la sostanza del requisito GT è "atterrata" nella risposta.

            ESEMPIO:
            - REQUISITO GT: "L'indennizzo è dovuto entro 60 giorni dalla notifica."
            - RISPOSTA: "Il cliente riceverà il rimborso." -> SCORE 0.5 (Manca la tempistica critica).
            - RISPOSTA: "Il pagamento avviene a 60 giorni." -> SCORE 1.0 (Sostanza preservata).

            SCALA DI VALUTAZIONE (0, 0.25, 0.5, 0.75, 1.0):
            1.0: Il requisito è totalmente coperto.
            0.75: Il requisito è coperto, ma manca un dettaglio non essenziale.
            0.5: Copertura parziale (il concetto principale c'è, ma mancano parametri chiave).
            0.25: Accenno vago al requisito senza sostanza informativa.
            0.0: Requisito completamente omesso o ignorato.

            Rispondi in JSON: {{"score": float, "motivation": "Analisi della copertura del requisito"}}
            """
            return {"claim": gc, **self._execute_evaluation(prompt)}

        with concurrent.futures.ThreadPoolExecutor() as executor:
            analysis = list(executor.map(eval_recall_item, gt_claims))
        
        total = sum(item["score"] for item in analysis) / len(gt_claims)
        return {"total_score": total, "claims_analysis": analysis}

    def evaluate_faithfulness(self, answer: str, corpus: str) -> Dict:
        """Faithfulness (Grounding): Previene l'uso di conoscenza esterna o allucinazioni."""
        ans_claims = self.split_claims(answer)
        if not ans_claims: return {"total_score": 0.0, "claims_analysis": []}
        
        analysis = []
        chunks = list(self.chunk_text(corpus, self.CHUNK_SIZE))

        for c in ans_claims:
            best_res = {"score": 0.0, "motivation": "Nessun supporto testuale trovato nel corpus documentale."}
            
            # Ottimizzazione: Short-circuit se troviamo un match perfetto
            for chunk in chunks:
                prompt = f"""
                ANALISI DI FAITHFULNESS (Ancoraggio al Testo)
                CONTESTO (DOCUMENTI): {chunk}
                CLAIM: "{c}"

                DEFINIZIONE RIGOROSA: Il claim deve essere supportato ESCLUSIVAMENTE dai documenti forniti.
                - Se il claim è vero nel mondo reale ma NON è presente nei documenti -> SCORE 0.0.
                - Se il claim è un'inferenza logica complessa non esplicitata -> SCORE 0.25.
                - Penalizza l'uso di "conoscenza generale" dell'AI.

                SCALA DI VALUTAZIONE (0, 0.25, 0.5, 0.75, 1.0):
                1.0: Supporto testuale diretto e inequivocabile.
                0.75: Supporto tramite parafrasi fedele.
                0.5: Supporto parziale (il testo parla del tema ma non conferma tutti i dettagli del claim).
                0.0: Allucinazione o informazione basata su conoscenza esterna al corpus.

                Rispondi in JSON: {{"score": float, "motivation": "Analisi dell'evidenza testuale"}}
                """
                res = self._execute_evaluation(prompt)
                if res["score"] > best_res["score"]:
                    best_res = res
                if best_res["score"] >= 1.0: break # Efficienza: smetti di cercare se il claim è confermato
            
            analysis.append({"claim": c, "score": best_res["score"], "reason": best_res["motivation"]})
        
        total = sum(item["score"] for item in analysis) / len(ans_claims)
        return {"total_score": total, "claims_analysis": analysis}

    def evaluate_consistency(self, answer: str) -> Dict:
        """Consistency (Coerenza): Analisi logica delle auto-contraddizioni."""
        claims = self.split_claims(answer)
        if len(claims) <= 1: return {"total_score": 1.0, "claims_analysis": [{"reason": "Dichiarazione univoca."}]}
        
        prompt = f"""
        ANALISI DI CONSISTENZA LOGICO-GIURIDICA
        ELENCO DICHIARAZIONI NELLA RISPOSTA:
        {json.dumps(claims, indent=2, ensure_ascii=False)}

        DEFINIZIONE: Esistono antinomie o conflitti logici tra queste affermazioni?
        ESEMPIO:
        - Punto 1: "L'accesso è consentito solo ai maggiorenni."
        - Punto 2: "Gli studenti di 16 anni possono accedere."
        - RISULTATO: Incoerenza totale (Score 0.0).

        SCALA DI VALUTAZIONE (0, 0.25, 0.5, 0.75, 1.0):
        1.0: Perfetta armonia logica tra tutti i punti.
        0.5: Contraddizione minore o ambiguità che richiede interpretazione.
        0.0: Contraddizione frontale (Antinomia).

        Rispondi in JSON: {{"score": float, "motivation": "Dettaglio del conflitto logico o della coerenza"}}
        """
        res = self._execute_evaluation(prompt, "Sei un esperto di logica e interpretazione dei trattati.")
        return {"total_score": res.get("score", 0.0), "analysis": res.get("motivation")}

    # -----------------------------
    # HELPERS
    # -----------------------------
    def split_claims(self, text: str) -> List[str]:
        """
        Scompone il testo in unità informative fondamentali con un limite massimo.
        """
        word_count = len(text.split())
        max_claims = max(1, min(25, word_count // 40))

        prompt = f"""
        Agisci come un analista legale esperto. Scomponi il seguente testo in una lista di 'atomi informativi' (claim) indipendenti.
        
        REGOLE DI ESTRAZIONE:
        1. Estrai solo i punti legalmente rilevanti (obblighi, scadenze, definizioni, divieti).
        2. LIMITAZIONE: Non generare più di {max_claims} punti. 
        3. Se il testo è complesso, raggruppa le informazioni secondarie in claim più densi invece di creare molti punti atomici.
        4. Rispondi solo con la lista, un claim per riga, senza introduzioni.

        Testo:
        {text}
        """
        
        response = client.chat.completions.create(
            model=self.MODEL, 
            messages=[{"role": "user", "content": prompt}], 
            temperature=0
        )
        
        # Estrazione e pulizia
        all_claims = [c.strip("- *") for c in response.choices[0].message.content.strip().split("\n") if len(c.strip()) > 5]
        
        # Ulteriore sicurezza: troncamento forzato lato Python
        return all_claims[:max_claims]

    def chunk_text(self, text, size):
        words = text.split()
        for i in range(0, len(words), size):
            yield " ".join(words[i:i + size])

    def judge(self, question, answer, ground_truth):
        corpus = "\n".join([str(doc) for doc in self.documents])
        
        # Parallelizzazione massiva per ridurre i tempi di attesa
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            fut_p = executor.submit(self.evaluate_precision, answer, ground_truth)
            fut_r = executor.submit(self.evaluate_recall, answer, ground_truth)
            fut_f = executor.submit(self.evaluate_faithfulness, answer, corpus)
            fut_cons = executor.submit(self.evaluate_consistency, answer)

            results = {
                "precision": fut_p.result(),
                "recall": fut_r.result(),
                "faithfulness": fut_f.result(),
                "consistency": fut_cons.result()
            }
        
        return results
            
    def initialize(self, paths):
        self.documents = []
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                self.documents.append(json.load(f))