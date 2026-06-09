import type {
  ChainPath,
  EncounterDetail,
  PeopleSearchResponse,
  PersonSearchItem,
  ReadyResponse,
  ShortestChainResponse,
} from "@/lib/figure-chain-types";

export const xuJi: PersonSearchItem = {
  person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
  display_name: "許幾",
  primary_name_zh_hant: "許幾",
  primary_name_zh_hans: "许几",
  primary_name_romanized: "Xu Ji",
  birth_year: 1054,
  death_year: 1115,
  index_year: 780,
  dynasty_code: null,
  matching_aliases: [],
  external_ids: ["780"],
};

export const hanQi: PersonSearchItem = {
  person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
  display_name: "韓琦",
  primary_name_zh_hant: "韓琦",
  primary_name_zh_hans: "韩琦",
  primary_name_romanized: "Han Qi",
  birth_year: 1008,
  death_year: 1075,
  index_year: 630,
  dynasty_code: null,
  matching_aliases: [],
  external_ids: ["630"],
};

export const peopleSearchResponse: PeopleSearchResponse = {
  query: "許幾",
  limit: 10,
  items: [xuJi],
};

export const oneHopPath: ChainPath = {
  length: 1,
  people: [
    {
      person_id: xuJi.person_id,
      display_name: xuJi.display_name,
      birth_year: xuJi.birth_year,
      death_year: xuJi.death_year,
      cbdb_external_id: "780",
    },
    {
      person_id: hanQi.person_id,
      display_name: hanQi.display_name,
      birth_year: hanQi.birth_year,
      death_year: hanQi.death_year,
      cbdb_external_id: "630",
    },
  ],
  edges: [
    {
      encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
      encounter_kind: "direct_interaction",
      certainty_level: "high",
      pages: "11905",
      evidence_summary: "许几谒韩琦于魏",
    },
  ],
};

export const shortestChainFound: ShortestChainResponse = {
  status: "found",
  source_person_id: xuJi.person_id,
  target_person_id: hanQi.person_id,
  max_depth: 12,
  path: oneHopPath,
};

export const shortestChainNoPath: ShortestChainResponse = {
  status: "no_path",
  source_person_id: xuJi.person_id,
  target_person_id: hanQi.person_id,
  max_depth: 12,
  path: null,
};

export const encounterDetail: EncounterDetail = {
  encounter_id: "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
  status: "active",
  encounter_kind: "direct_interaction",
  certainty_level: "high",
  path_eligible: true,
  source_work_id: 7596,
  pages: "11905",
  evidence_summary: "许几谒韩琦于魏",
  review_note: null,
  reviewed_by: "lyl",
  reviewed_at: "2026-06-09T00:00:00Z",
  person_a: {
    person_id: xuJi.person_id,
    cbdb_id: 780,
    display_name: xuJi.display_name,
    primary_name_zh_hant: xuJi.primary_name_zh_hant,
    primary_name_zh_hans: xuJi.primary_name_zh_hans,
    primary_name_romanized: xuJi.primary_name_romanized,
    birth_year: xuJi.birth_year,
    death_year: xuJi.death_year,
    external_ids: ["780"],
  },
  person_b: {
    person_id: hanQi.person_id,
    cbdb_id: 630,
    display_name: hanQi.display_name,
    primary_name_zh_hant: hanQi.primary_name_zh_hant,
    primary_name_zh_hans: hanQi.primary_name_zh_hans,
    primary_name_romanized: hanQi.primary_name_romanized,
    birth_year: hanQi.birth_year,
    death_year: hanQi.death_year,
    external_ids: ["630"],
  },
  evidence: [
    {
      evidence_id: 12,
      candidate_table: "relationship_candidates",
      candidate_id: 960664,
      source_ref_id: 3853784,
      source_work_id: 7596,
      pages: "11905",
      evidence_kind: "candidate",
      evidence_summary: "许几谒韩琦于魏",
      created_at: "2026-06-09T00:00:00Z",
    },
  ],
  source_refs: [
    {
      source_ref_id: 3853784,
      source_work_id: 7596,
      title_zh: null,
      title_en: null,
      pages: "11905",
      notes: "字先之，贵溪人，以诸生谒韩琦于魏。",
    },
  ],
};

export const readyResponse: ReadyResponse = {
  status: "ready",
  dependencies: {
    postgresql: { status: "ok" },
    neo4j: { status: "ok" },
  },
};
