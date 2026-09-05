---
name: writing-quality
description: Draft or revise user-facing Korean or English text when writing quality is a material part of success. Use for analytical essays, long-form or recurring evidence-backed research, business-model or mechanism analysis, investment research, technical explanation, publish-ready HTML/CSS articles, relationship-sensitive cooperation requests, business messages, prompts, literary prose, or edits, especially when the user requests voice preservation, higher information density, careful revision, or publication-ready quality. Do not invoke solely because an answer is prose, uses sources, or needs factual verification; skip short atomic source-backed Q&A unless the user explicitly requests writing, revision, or publication-quality work.
---

# Writing Quality

문체를 문장 표면의 습관으로 복제하지 말고, 무엇을 남기고 어떤 순서로 보여줄지 판단한 결과로 재현하라. 독자가 대상을 더 정확히 이해하고 바로 판단하거나 행동할 수 있는 글을 완성하라.

## 호출 경계

1. 모든 사용자 대상 답변은 전역 지침의 최소 글쓰기 기준을 지킨다. 이 스킬은 글쓰기 자체가 품질 병목일 때만 추가한다.
2. 독자가 그대로 읽거나 보내거나 게시할 원고가 주요 산출물일 때 사용한다.
3. 사용자가 문체·목소리·완성도 개선을 명시하거나, 장문·반복 발행·오독 비용이 큰 근거 기반 답변에서 별도 설계와 퇴고가 실질적으로 품질을 높이면 채팅 응답에도 사용한다.
4. 답변이 문장 형식이거나 출처를 쓴다는 이유만으로 호출하지 않는다. 짧고 원자적인 출처 기반 질의응답은 직접 답한다.
5. 소프트웨어 변경이 중심이면 `software-engineering`이 작업·검증을 소유한다. 게시형 HTML에서 원고와 정보 구조는 이 스킬, 렌더링과 코드 검증은 software-engineering이 소유한다.

## 우선순위

1. 사용자의 명시적 목적·형식·길이·원문 보존 요구
2. 사실의 정확성, 논리, 필요한 맥락
3. 장르·독자·사용 환경에 맞는 구조
4. 문체와 리듬

문체를 위해 사실을 단정하거나 필요한 설명을 빼거나 요청 형식을 바꾸지 않는다.

## 핵심 원칙

- 핵심 답이나 중심 주장을 초반에 드러낸다. 서사나 관계 민감 메시지는 장르상 필요한 도입을 허용한다.
- 결론만 나열하지 말고 실제 작동 메커니즘과 빠지면 결론이 무너지는 인과 단계를 설명한다.
- 추상어보다 확인된 사실, 숫자, 날짜, 비교, 장면, 과정, 선택 조건을 우선한다.
- 사실, 추론, 가정, 미확인 영역을 구분한다.
- 문단마다 하나의 역할을 맡기고 앞의 논리를 진전시킨다.
- 짧음보다 밀도를 우선하되 이해와 검증에 필요한 추론까지 압축하지 않는다.
- 차분하고 직접적으로 쓴다. 약한 논리와 불확실성을 숨기지 않는다.
- 기존 원고를 고칠 때는 고유한 표현과 강한 문장을 보존하고 실제 개선이 있는 부분만 바꾼다.
- 결말은 도입을 반복하지 말고 판단, 남은 불확실성, 관찰 지표, 행동 요청, 또는 압축된 명제로 닫는다.

## 작성

과제 규모에 맞게 절차를 축소한다. 짧은 답변·단일 사실·한두 문장 교정에는 작업표나 분리 검수를 만들지 않는다.

비사소한 원고에서는 내부적으로 목적, 독자, 장르·사용 표면, 사실성 요구, 완료 조건을 정한다. 맥락이 충분하면 확인 질문 없이 진행한다.

구조는 `references/genre-playbooks.md`에서 지배적인 목적에 맞는 플레이북을 고른다. 장문 또는 반복 발행되는 근거 기반 조사 에세이는 그 문서의 `근거 기반 조사 에세이` 플레이북으로 독자가 답을 알아가는 순서를 먼저 설계하고, 중복·연대기·주장별 근거·인과 강도를 별도 관리할 실익이 크면 `references/evidence-backed-research-essay.md`를 함께 적용한다. 짧은 출처 기반 Q&A에는 적용하지 않는다.

관계 민감한 자발적 협조 요청에는 `references/recipient-centered-persuasion.md`를 적용한다. 의무·평가·징계·안전 지시를 호의적 조언처럼 꾸미지 않는다.

게시형 HTML/CSS 분석 아티클에는 `references/publishable-html-article.md`를 적용한다.

필요한 장문 분석에만 다음 내부 설계를 쓴다.

1. 직접 답할 한 문장
2. 핵심 메커니즘 또는 근거
3. 빠지면 결론이 무너지는 중간 단계
4. 가장 강한 반대 근거나 경계 조건
5. 도달할 판단·행동·여운

모든 칸을 기계적으로 본문 문단으로 만들지 않는다.

## 검수

초안 뒤에 다음을 확인한다.

- 중심 질문에 실제로 답했는가
- 사실·수치·날짜·비교축과 인과 강도가 맞는가
- 빠진 인과 단계나 범위가 흐린 주장이 있는가
- 같은 역할의 문장·문단을 반복하는가
- 주어·지시어·용어의 경계가 분명한가
- 조사 과정의 URL·도구 표식·JSON·raw marker가 독자용 본문에 새지 않았는가
- 장르와 맞지 않는 템플릿 습관이 남았는가

근거 기반 장문 조사에서 분리 검수가 실질적으로 가치 있으면 `agents/research_fact_reviewer.md`와 요청 언어에 맞는 editor를 사용한다. 독립 검수가 불가능하면 self-review를 독립 검수로 표현하지 않는다.

조사 에세이의 언어 편집은 문제 목록을 만드는 것으로 끝내지 않는다. 사실 검수에서 확정한 내용과 주장 강도를 보존한 **수정된 전체 원고**를 만들어야 한다. 구조 문제가 있으면 문단 삭제·통합·재배열과 도입·결말 재작성을 허용하고, 수정 뒤에는 작성 과정의 맥락을 모르는 독자처럼 콜드 리드해 중간 논리를 독자가 스스로 메워야 하는 곳이 없는지 확인한다.

사용자가 한 표현이나 시각 요소를 지적하면 구체 문구가 아니라 실패 유형을 일반화해 관련 범위에서 같은 문제를 고친다. 단, 한 번의 수정 때문에 영구 규칙·테스트·평가 세트를 자동으로 늘리지 않는다.

## 문장과 수사

- 한국어는 장르에 맞는 자연스럽고 단정적인 문장을 쓴다. 영어는 한국어 문장 구조를 옮기지 않는다.
- 번역 가능한 전문 용어는 자연스러운 한국어를 우선하고, 정확한 원어가 필요할 때만 첫 등장에 병기한다.
- 제목은 본문이 실제로 입증한 변화·메커니즘·판단을 근거의 강도로 압축한다.
- 대조는 실제 혼동하기 쉬운 두 개념의 경계를 그을 때만 쓴다.
- 비유는 문자 설명보다 정확하고 짧을 때만 사용한다.
- 전문 용어는 정밀도를 높일 때만 쓰고 처음 등장할 때 작동 방식으로 푼다.
- 상투적 도입·결론과 근거 없는 `본질`, `혁신`, `압도적`, `시너지` 같은 추상 강조를 피한다.

## 편집

사실 오류, 논리 오류, 불명확성, 리듬 문제, 취향을 구분한다. 국소 수정으로 해결되면 전체를 다시 쓰지 않는다. 다만 장문·게시용·반복 발행 원고에서 구조가 독자의 이해를 방해하면 원래 문단 순서를 보존하는 것보다 재구성을 우선한다. 사용자가 최종으로 확정한 원고는 명백한 오류가 없는 한 추가 교정을 강요하지 않는다.

완성 원고를 요청하면 산출물을 먼저 제공한다. 피드백·검수 요청에는 우선순위가 높은 문제부터 설명한다. 요청한 언어·형식·길이를 지킨다.

## 참고 자료

- `references/genre-playbooks.md`
- `references/evidence-backed-research-essay.md`
- `references/review-rubric.md`
- `references/recipient-centered-persuasion.md`
- `references/publishable-html-article.md`
- `references/reader-first-information-design-examples.md`
- `agents/research_fact_reviewer.md`
- `agents/korean_research_editor.md`
- `agents/english_research_editor.md`
