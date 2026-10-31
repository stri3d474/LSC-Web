---
inclusion: always
---
# LSC Domain Rules

LSC is an independent language, not signed Spanish. It has spatial grammar, topic-comment order, simultaneous morphology (handshape, movement, location and face carry meaning together), usually no articles or copula, and non-manual markers (NMM): eyebrow raise/furrow (questions), mouth morphemes, head nod/shake (agreement/negation).

Variation is real (region, education level, context; e.g. the sign for "ciencias" differs in school vs university). Never choose one "correct" variant. Store all variants and map them to one Concept.

## Glossary (use these exact words in code and docs)
- Concept: language-neutral meaning (`concept_id`).
- Variant: one specific signed form of a Concept, tagged with region_codes, contexts, education_level (`variant_id`).
- Gloss: uppercase written label of a sign, e.g. DOLOR, NO-ENTIENDO.
- Take: one repetition of a sign. Clip: one recorded video file.
- Sequence: normalized landmark array of one take, shape [T, F].
- Package: versioned model bundle (C2). Token: one recognized sign with confidence and timing (C3).

## Codes
- Regions: BOG MED BAQ CAL BUC OTR. Contexts: MED ESC UNI JUR GEN. Environment: CTR (controlled) DCT (uncontrolled).
- Interpreters: INT01..INT03. Education level: school | university | unspecified.

## Dataset protocol
- 60 takes per sign per interpreter: 30 CTR + 30 DCT, recorded as continuous video with visible 1-2 s rest pauses (hands down) between takes.
- File name: `{SIGN}_{INT_ID}_{REGION}_{CONTEXT}_{ENV}.mp4`, e.g. `DOLOR_INT01_BOG_MED_CTR.mp4`. SIGN = uppercase letters A-Z and Ñ, digits, hyphen (multi-word signs use hyphen, never underscore). No other accents.
- Variation axes: position, speed, camera distance, camera angle, sleeve length, glasses, lighting, background.
- 200-sign vocabulary in 3 priority phases; advance to the next vocabulary phase only at >= 85% accuracy on a signer unseen in training.
- Quality bar: generalize to unseen signers and unseen environments. Dataset quality beats quantity.
