# 경계 행동 차등 평가

출처: PR #45 review comment `3888862985`

비교 대상:

- pre-fix: `032b5b1cd9ae11ac6bc826807bf62eade30196dd`
- candidate: `c90adb5b589232c518c8b608f5247621f6885697`

공통 실행 조건:

- 모델: GPT-5.6 Sol
- 추론 수준: 실행 API가 명명된 값을 노출하지 않아 동일 플랫폼 기본값으로 기록
- `fork_turns=none`
- 네트워크 금지
- 파일 수정 금지
- 여섯 실행 모두 `completed`

각 실행의 전체 프롬프트는 해당 변형 머리말, 빈 줄 두 개, 사례 입력을 연결한 것이다.

pre-fix 머리말:

```text
You are one isolated behavior-evaluation execution. Treat `/tmp/dak-boundary-eval-20260830/pre-fix` as the complete project workspace and obey the AGENTS.md and skill resources from that snapshot, not those from `/workspace/davis-agent-kit`. Do not modify any file, do not browse, and do not inspect the candidate snapshot. Execute the user input below as the task. Return only the complete user-facing output you would give for that input, with no evaluator commentary or summary.
```

candidate 머리말:

```text
You are one isolated behavior-evaluation execution. Treat `/tmp/dak-boundary-eval-20260830/candidate` as the complete project workspace and obey the AGENTS.md and skill resources from that snapshot, not those from `/workspace/davis-agent-kit`. Do not modify any file, do not browse, and do not inspect the pre-fix snapshot. Execute the user input below as the task. Return only the complete user-facing output you would give for that input, with no evaluator commentary or summary.
```

## 사례 1: 짧은 출처 기반 질의응답

### 동일 입력

```text
다음 제공 자료만 사용하고 외부 조회는 하지 마세요. 질문에 한국어 두 문단 이내로 직접 답하세요. 확인된 사실과 자료에서 직접 확인할 수 없는 추론을 구분하세요.

[공식 문서 발췌]
Acme CLI 4.2 명령어 참고서: `acme sync`는 실제 변경 없이 예정된 작업만 출력하는 `--dry-run` 옵션을 지원한다. 이 옵션은 원격 또는 로컬 파일을 변경하지 않으며 종료 코드는 실제 동기화와 같은 검증 규칙을 따른다.

질문: Acme CLI 4.2의 `acme sync`는 dry run을 지원하나요? 지원한다면 무엇을 보장하나요?
```

### 판정 기준

출처 사용만으로 무거운 조사 프로필을 출력 표면에 적용하지 않고 주제 원장·다섯 줄 설계·주장표·사건표·분리 편집을 노출하지 않으며, 필요한 사실 확인과 사실·추론 경계를 지켜 두 문단 이내로 직접 답하는가.

### pre-fix 원출력

```text
확인된 사실: 네, Acme CLI 4.2의 `acme sync`는 `--dry-run`을 지원합니다. 이 옵션은 실제 변경 없이 예정된 작업만 출력하며, 원격 파일과 로컬 파일을 변경하지 않습니다. 또한 종료 코드는 실제 동기화와 동일한 검증 규칙을 따릅니다. 제공된 자료를 넘어서는 추론은 없습니다.
```

판정: `PASS (출력 표면)`. 무거운 작업물이 없고 한 문단으로 직접 답했다. 내부 프로필 선택은 최종 출력만으로 관측할 수 없으므로 적용하지 않았다고 단정하지 않는다.

### candidate 원출력

```text
네, Acme CLI 4.2의 `acme sync`는 `--dry-run`을 지원합니다. **확인된 사실:** 이 옵션은 예정된 작업만 출력하며 원격 및 로컬 파일을 실제로 변경하지 않습니다. 종료 코드는 실제 동기화와 동일한 검증 규칙을 따릅니다. 제공 자료에서 직접 확인할 수 없는 추가 추론은 없습니다.
```

판정: `PASS (출력 표면)`. 무거운 작업물이 없고 한 문단으로 직접 답했다. 내부 프로필 선택은 최종 출력만으로 관측할 수 없으므로 적용하지 않았다고 단정하지 않는다.

차이: 표현 차이만 있고 평가 대상 행동의 실제 출력 차이는 관측되지 않았다.

## 사례 2: 시간축 없는 조사 글

### 동일 입력

```text
아래에 제공한 횡단면 자료와 방법론 설명만 사용해, 관측된 집단 차이가 무엇을 말하고 무엇을 말하지 못하는지 한국어로 900~1,200자 분량의 출고 가능한 조사 분석문을 작성하세요. 외부 조회는 하지 마세요. 완성 원고 뒤에는 독자용 본문과 분리된 `검수 기록`을 붙여 실제로 적용한 글쓰기 프로필, 중심 주장과 주장별 근거, 사건표 적용 여부와 이유, 사실 검수 판정, 선택한 편집기 파일 이름을 기록하세요. 형식만 채우기 위한 사실이나 시간 순서를 만들어내지 마세요.

[자료]
- 같은 한 차례의 설문에서 집단 A 100명 중 62명, 집단 B 100명 중 44명이 기능 X를 사용한다고 응답했다.
- 표본은 자발적으로 참여한 편의표본이며 모집단을 대표하도록 설계되지 않았다.
- 집단 A와 B는 연령 구성과 직무 구성이 달랐다.
- 기능 X 사용 여부는 자기보고로 측정했으며 사용 기록으로 검증하지 않았다.
- 연구자는 집단 배정을 무작위화하거나 다른 변수를 통제하지 않았다.
- 자료에는 날짜, 기간, 이전 측정, 후속 측정, 변화량 또는 사건 순서가 없다.
```

### 판정 기준

장문·오독 비용에 맞게 조사 프로필과 주장 근거를 적용하되, 숨은 시간 비교가 없음을 확인하고 사건표를 `해당 없음` 또는 의미상 동등한 판정과 이유로 처리하며, 가짜 날짜·순서를 만들지 않고 사실 검수를 통과시키고 한국어 편집기를 선택하는가.

### pre-fix 원출력

```text
### 18%포인트 차이는 관측됐지만 원인은 확인되지 않았다

이번 설문에서는 집단 A 응답자 100명 중 62명, 집단 B 응답자 100명 중 44명이 기능 X를 사용한다고 답했다. 각 표본 안의 자기보고 비율은 각각 62%와 44%이며, 관측된 차이는 18%포인트다. 따라서 이 자료가 직접 말하는 것은 “이 설문에 자발적으로 참여한 A 응답자에게서 X 사용 응답이 B 응답자보다 더 많았다”는 사실이다. 같은 크기의 표본에서 응답 인원도 18명 더 많다.

그러나 이 차이를 두 집단 일반의 차이로 곧바로 넓힐 수는 없다. 표본은 모집단 대표성을 목표로 뽑은 확률표본이 아니라 자발적 편의표본이다. 참여 여부가 기능 X에 대한 관심이나 사용 경험과 관련돼 있다면, 두 표본의 응답 비율은 각 모집단의 실제 사용률과 다를 수 있다. 표본 수가 집단별로 100명이라는 사실은 관측 비율 계산에는 충분하지만, 선택 편향을 없애거나 대표성을 만들어 주지는 않는다.

원인도 판별할 수 없다. A와 B는 연령 및 직무 구성이 다르고, 연구자는 집단을 무작위로 배정하거나 다른 변수를 통제하지 않았다. 관측된 18%포인트가 집단 자체의 특성 때문인지, 연령·직무 구성 때문인지, 또는 측정되지 않은 다른 요인 때문인지 이 자료만으로 분리할 수 없다. 따라서 “A에 속하면 X를 더 사용하게 된다”거나 특정 집단 특성이 사용을 증가시킨다는 인과 결론은 성립하지 않는다.

측정의 범위도 제한적이다. 기능 X 사용은 실제 기록이 아니라 응답자의 자기보고이므로 기억 오류, ‘사용’에 대한 해석 차이, 응답 성향이 결과에 섞였을 수 있다. 이 수치는 검증된 실제 사용률이 아니라 설문 시점의 사용 응답률로 읽어야 한다. 또한 이전·후속 측정이나 기간 정보가 없으므로 사용이 늘었는지 줄었는지, 어느 집단이 먼저 변했는지, 차이가 지속되는지도 말할 수 없다.

이 결과의 적절한 용도는 인과나 모집단 추정의 확정이 아니라 후속 조사의 출발점이다. 대표성 있는 표집, 연령·직무를 고려한 비교, 일관된 사용 정의와 기록 검증, 필요하다면 반복 측정을 갖춘 뒤에야 집단 차이의 범위와 가능한 원인을 더 좁힐 수 있다. 현재 결론은 명확하다. 관측된 차이는 존재하지만, 그 차이의 일반성·원인·변화 방향은 확인되지 않았다.

---

## 검수 기록

- **적용한 글쓰기 프로필:** `근거 기반 조사 에세이 프로필`
- **중심 주장:** 제공된 횡단면 설문에서는 A의 기능 X 사용 응답률이 B보다 18%포인트 높았지만, 편의표집·집단 구성 차이·자기보고·비무작위 설계 때문에 모집단 차이, 인과관계, 시간에 따른 변화를 확인할 수 없다.
- **주장별 근거:**
  1. **표본 내 차이:** A 62/100, B 44/100이므로 각각 62%, 44%이며 차이는 18%포인트다.
  2. **일반화 제한:** 자발적 편의표본이며 모집단 대표성을 갖도록 설계되지 않았다.
  3. **인과 추론 제한:** 연령·직무 구성이 다르고 무작위 배정이나 다른 변수의 통제가 없었다.
  4. **측정 제한:** 사용 여부가 검증된 기록이 아닌 자기보고다.
  5. **변화·순서 판단 불가:** 날짜, 기간, 이전·후속 측정, 변화량, 사건 순서가 제공되지 않았다.
- **사건표 적용 여부:** 적용하지 않음. 시간축을 구성할 자료가 전혀 없어 사건표를 만들면 형식만 채우거나 순서를 창작하게 된다.
- **사실 검수 판정:** 제공 자료 범위에서 통과. 비율과 18%포인트 차이를 재계산했고, 관측값·추론·미확인 영역을 구분했다. 외부 사실은 추가하지 않았으며 해결되지 않은 P1·P2 지적은 없다.
- **선택한 편집기 파일 이름:** `korean_research_editor.md`
```

판정: `PASS`. 사건표를 적용하지 않은 이유를 기록했고, 가짜 순서를 만들지 않았으며 사실 검수 통과와 한국어 편집기 선택을 명시했다.

### candidate 원출력

```text
### 18%포인트 차이는 관측됐지만, 원인이나 모집단 차이는 확인되지 않았다

한 차례의 설문에서 기능 X를 사용한다고 답한 비율은 집단 A가 62%(100명 중 62명), 집단 B가 44%(100명 중 44명)였다. 따라서 이 표본에서 관측된 집단 간 차이는 18%포인트이며, 방향은 A가 B보다 높다. 이는 조사에 참여한 200명의 응답을 기술하는 명확한 결과다. 다만 이 수치는 두 집단의 본질적 성향이나 기능 X의 효과를 보여주는 값이 아니라, 특정 편의표본에서 한 시점에 얻은 자기보고 응답의 차이다.

이 차이를 모집단 전체로 일반화하기는 어렵다. 표본은 자발적으로 참여한 사람들로 구성됐고 모집단 대표성을 갖도록 설계되지 않았다. 기능 X에 관심이 많거나 사용 사실을 더 적극적으로 밝히는 사람이 집단별로 다르게 참여했을 가능성을 자료만으로 배제할 수 없다. 또한 자기보고는 실제 사용 기록과 일치하는지 검증되지 않았으므로, 응답 기억이나 ‘사용’의 해석 차이가 측정값에 섞였을 수 있다. 따라서 62%와 44%는 실제 사용률 자체가 아니라 ‘사용한다고 응답한 비율’로 읽어야 한다.

집단 구성의 차이도 해석의 핵심 한계다. A와 B는 연령과 직무 구성이 달랐고, 연구자는 이를 포함한 다른 변수를 통제하지 않았다. 연령이나 직무가 기능 X를 접할 기회, 업무상 필요, 사용 습관과 관련돼 있다면 관측된 18%포인트 가운데 일부 또는 전부가 집단 구분이 아니라 구성 차이와 연결될 수 있다. 어느 요인이 얼마나 기여했는지는 제공된 자료로 분리할 수 없다. 무작위 배정도 없었으므로 집단 소속이 기능 사용을 늘리거나 줄였다는 인과 결론 역시 성립하지 않는다.

이 설문이 말하는 범위는 제한적이지만 분명하다. 참여자 안에서는 A의 자기보고 사용 비율이 B보다 높았다. 반면 모집단에서도 같은 격차가 존재하는지, 실제 사용 기록에서도 재현되는지, 왜 차이가 생겼는지, 시간이 지나며 격차가 변했는지는 알 수 없다. 다음 판단에는 대표성을 고려한 표집, 연령·직무가 비슷한 집단 간 비교 또는 통계적 조정, 객관적 사용 기록이 필요하다. 인과를 묻는다면 무작위화나 그에 준하는 식별 설계가 추가돼야 한다.

---

## 검수 기록

- **적용한 글쓰기 프로필:** `근거 기반 조사 에세이 프로필`
- **중심 주장:** 이 편의표본에서는 A의 자기보고 사용 비율이 B보다 18%포인트 높았지만, 이 결과만으로 모집단 차이·실제 사용률 차이·원인·시간에 따른 변화를 판단할 수 없다.
- **주장별 근거:**
  1. **표본 내 차이:** A 62/100, B 44/100에서 18%포인트를 계산했다.
  2. **일반화 제한:** 자발적 편의표본이며 대표 표집으로 설계되지 않았다.
  3. **측정 제한:** 사용 여부가 자기보고이고 사용 기록으로 검증되지 않았다.
  4. **인과 해석 제한:** 연령·직무 구성이 다르고 무작위 배정과 변수 통제가 없었다.
  5. **변화 해석 제한:** 날짜·기간·이전 및 후속 측정·변화량·사건 순서가 없다.
- **사건표:** 해당 없음. 자료와 본문에 날짜, 기간, 사건 순서 또는 관측된 변화 주장이 없으며, 시간에 따른 변화는 알 수 없는 항목으로만 명시했다.
- **사실 검수 판정:** 통과. 제공 자료와 수치·분모·측정 방식·표본 범위·인과 강도를 대조했으며 해결되지 않은 P1·P2는 없다. 외부 검증은 수행하지 않았다.
- **선택한 편집기 파일:** `korean_research_editor.md`
```

판정: `PASS`. 사건표를 `해당 없음`으로 표시하고 이유를 기록했으며, 가짜 순서를 만들지 않았고 사실 검수 통과와 한국어 편집기 선택을 명시했다.

차이: candidate만 `해당 없음`을 문자 그대로 썼지만 pre-fix도 의미상 동일한 판정·이유·통과를 냈다. 기대 경계 행동의 실제 차이는 관측되지 않았다.

## 사례 3: 영어 조사 글 편집

### 동일 입력

```text
Using only the supplied claims, source notes, and completed factual review, turn the draft into a publication-ready evidence-backed research essay in English. Do not browse or add facts. After the essay, add a separate `Editing record` that names the editor file actually selected, lists the material English-language problems found, states whether the Korean research editor was applied, and identifies any revision that requires factual re-review.

[Approved central claim]
In this cross-sectional convenience sample, reported adoption was higher in Group A than in Group B, but the design does not establish that group membership caused the difference.

[Source notes]
- One survey wave: Group A, 62 of 100 respondents; Group B, 44 of 100 respondents.
- Participation was voluntary, the sample was not designed to represent a population, and the groups differed in age and job mix.
- Adoption was self-reported and not checked against usage logs.
- There was no random assignment or adjustment for other variables.
- There are no dates, periods, before/after measures, changes, or event sequence in the evidence.

[Completed factual review]
The central claim and both counts are supported. The 18-percentage-point descriptive gap may be reported. Causal, temporal, and population-wide claims are not permitted. There are no unresolved factual findings.

[Draft]
About the adoption difference confirmation

In this research, what we can confirm is the existence of adoption difference. Group A was showing 62% utilization, while Group B was showing 44% usage ratio. Through this, the causality of group belonging cannot be said, and the generalization execution is difficult.

The voluntary participation and the age and job composition difference make a representativeness limitation formation. Also, because adoption was self-report, actual-use confirmation was not performed. [Search result: Survey dashboard] https://example.invalid/raw TOOL_CALL{"open":"notes"}

In conclusion, an 18-point gap exists. In conclusion, this meaningful gap gives an important implication for strategy, but more verification is needed.
```

### 판정 기준

사실 검수 뒤 영어 편집기를 선택하고 한국어 편집기를 적용하지 않으며, 한국어 어순·직역 명사화·용어 불일치·URL·도구 표면 잔재를 영어 편집 문제로 처리하고, 주장 강도·수치·시간·비교·인과를 바꾸는 수정만 사실 재검수로 돌리는가.

### pre-fix 원출력

```text
# Reported Adoption Differed Between the Groups, but the Evidence Is Descriptive

In this cross-sectional convenience sample, 62 of 100 respondents in Group A reported adoption, compared with 44 of 100 respondents in Group B. The observed difference was therefore 18 percentage points. This result establishes a descriptive gap within the sample: reported adoption was higher in Group A than in Group B.

The study design does not establish that group membership caused the difference. Participation was voluntary, the sample was not designed to represent a broader population, and the groups differed in their age and job composition. Moreover, respondents were not randomly assigned to the groups, and the analysis did not adjust for other variables. The evidence therefore cannot separate group membership from these other differences as an explanation for the reported gap.

Measurement also limits the interpretation. Adoption was self-reported and was not verified against usage logs, so the figures describe respondents’ reports rather than independently confirmed use. Because the evidence contains no dates, periods, before-and-after measures, changes, or event sequence, it also supports no claim about when the difference emerged or how adoption developed.

The defensible conclusion is narrow but clear: this sample contains an 18-percentage-point difference in reported adoption between the two groups. The finding may justify further investigation, but it does not support causal, temporal, or population-wide conclusions.

## Editing record

- **Editor file selected:** None. No dedicated English-language research editor file was available in the supplied resources.
- **Material English-language problems found:** The draft had an unclear title; unidiomatic phrases such as “difference confirmation,” “generalization execution,” and “representativeness limitation formation”; inconsistent use of *adoption*, *utilization*, *usage*, and *usage ratio*; awkward progressive constructions; an imprecise causal statement; duplicated conclusion language; an unsupported characterization of the gap as “meaningful”; an unsupported strategic implication; and leaked research-process artifacts, including a search-result label, invalid URL, and tool-call text.
- **Korean research editor applied:** No. `skills/writing-quality/agents/korean_research_editor.md` targets Korean-language research essays and was not applied to this English-language manuscript.
- **Revisions requiring factual re-review:** None. The revision preserves the approved central claim, both supported counts, the approved 18-percentage-point calculation, and the stated design and measurement limitations; it adds no new factual claims.
```

판정: `FAIL`. 한국어 편집기는 적용하지 않았고 영어 문제도 고쳤지만, 전용 영어 편집기를 선택하지 못했다.

### candidate 원출력

```text
# A Descriptive Difference in Reported Adoption

In this cross-sectional convenience sample, reported adoption was higher in Group A than in Group B. Of the 100 respondents in each group, 62 respondents in Group A reported adoption, compared with 44 respondents in Group B. This is a descriptive gap of 18 percentage points.

The comparison does not establish that group membership caused the difference. Participation was voluntary, the sample was not designed to represent a broader population, and the groups differed in their age and job composition. Because respondents were not randomly assigned and the analysis did not adjust for other variables, these differences could not be separated from the effect of group membership.

The measure itself also limits the conclusion. Adoption was self-reported and was not verified against usage logs, so the findings describe respondents’ reports rather than confirmed use. In addition, the evidence contains only one survey wave and provides no basis for claims about changes over time, before-and-after effects, or the sequence of events.

The supported conclusion is therefore narrow but clear: reported adoption differed between the two groups in this sample. The 18-percentage-point gap is valid as a descriptive result, but it does not support causal, temporal, or population-wide claims.

## Editing record

- **Editor selected:** `skills/writing-quality/agents/english_research_editor.md`
- **Material English-language problems found:** a vague and non-idiomatic title; translated constructions such as “generalization execution” and “representativeness limitation formation”; inconsistent terms for the outcome (“adoption,” “utilization,” and “usage ratio”); unclear phrasing of the causal limitation; a raw search-result label, invalid URL, and tool-call residue in the reader-facing text; repetition of the conclusion; and unsupported descriptions of the gap as “meaningful” and strategically important.
- **Korean research editor applied:** No. The requested output language was English.
- **Revisions requiring factual re-review:** None. The revisions preserved the approved counts, the 18-percentage-point comparison, the measurement limitations, and the permitted causal scope without introducing new factual claims.
```

판정: `PASS`. `english_research_editor.md`를 선택하고 한국어 편집기를 배제했으며, 영어 문제와 출력 표면 잔재를 제거하면서 사실 범위를 보존했다.

차이: 실제 평가 대상 출력 차이가 있었다. pre-fix는 전용 영어 편집기를 선택하지 못했고 candidate는 영어 편집기를 명시적으로 선택했다.

## 종합

- pre-fix: `PASS / PASS / FAIL`
- candidate: `PASS / PASS / PASS`
- 실제로 관측된 행동 개선: 영어 편집기 라우팅
- 이 표본에서 관측되지 않은 차이: 짧은 질의응답 경계, 시간축 없는 사건표 경계

사례별 한 번의 대표 표본이므로 결정론적 보장으로 해석하지 않는다.
