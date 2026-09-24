import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = new URL(".", import.meta.url).pathname.replace(/^\//, "");
const data = JSON.parse(await fs.readFile(`${root}/case_study_data.json`, "utf8"));
const font = "Arial";
const blue = "#0F4C5C";
const light = "#EAF2F5";

function scalar(v) {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.map(scalar).join("; ");
  if (typeof v === "object") return JSON.stringify(v);
  return v;
}
function label(c) { return typeof c === "string" ? c : (c.label || "Value"); }
function value(r,c) { return scalar(typeof c === "function" ? c(r) : (typeof c === "object" ? c.get(r) : r[c])); }
function rows(records, columns) {
  return records.map(r => columns.map(c => value(r,c)));
}
async function book(filename, title, columns, records, note = "SYNTHETIC validation case. Results are evidence records, not compliance determinations.") {
  const wb = Workbook.create(); const sh = wb.worksheets.add("Results"); sh.showGridLines = false;
  sh.getRange("A1").values = [[title]]; sh.getRange("A2").values = [[note]];
  sh.getRangeByIndexes(3, 0, 1, columns.length).values = [columns.map(label)];
  sh.getRangeByIndexes(4, 0, Math.max(records.length,1), columns.length).values = records.length ? rows(records, columns) : [columns.map(()=>"")];
  const endCol = String.fromCharCode(64 + Math.min(columns.length, 26));
  sh.getRange(`A1:${endCol}1`).format.font = { name: font, size: 14, bold: true, color: blue };
  sh.getRange(`A2:${endCol}2`).format.font = { name: font, size: 10, italic: true, color: "#44546A" };
  sh.getRangeByIndexes(3,0,1,columns.length).format = { fill: blue, font:{name:font,size:10,bold:true,color:"#FFFFFF"}, horizontalAlignment:"center", verticalAlignment:"center", wrapText:true };
  sh.getRangeByIndexes(4,0,Math.max(records.length,1),columns.length).format = { font:{name:font,size:10}, verticalAlignment:"top", wrapText:true };
  sh.getRangeByIndexes(3,0,Math.max(records.length+1,2),columns.length).format.borders = { preset:"outside", style:"thin", color:"#B7C9D3" };
  sh.getRangeByIndexes(4,0,Math.max(records.length,1),columns.length).format.autofitColumns();
  sh.getRangeByIndexes(3,0,Math.max(records.length+1,2),columns.length).format.autofitRows();
  for(let c=0;c<columns.length;c++) sh.getRangeByIndexes(0,c,records.length+4,1).format.columnWidth = Math.min(35, Math.max(13, sh.getRangeByIndexes(4,c,1,1).format.columnWidth || 16));
  sh.freezePanes.freezeRows(4);
  wb.recalculate();
  const out = await SpreadsheetFile.exportXlsx(wb); await out.save(`${root}/${filename}`);
  return wb;
}

await book("synthetic_formulation.xlsx", "Synthetic formulation", ["name","cas","ec","concentration_percent","role"], data.formulation, "Synthetic industrial coating formulation. Concentrations are % w/w and total 100.0%.");
await book("identity_resolution.xlsx", "Identity resolution", ["input_name","input_cas","input_ec","matched_name","matched_cas","matched_ec","match_method","ambiguity_flag","manual_review_required"], data.identities);
await book("candidate_list_results.xlsx", "Candidate List / SVHC screening", ["status","matched_identifier","entry_number","summary","conditions_or_thresholds","review_notes","authority_level","effective_date","dataset_id"], data.candidate_list_results, "No match is limited to the checked curated snapshot. Candidate List membership does not itself decide obligations.");
await book("annex_xvii_results.xlsx", "REACH Annex XVII screening", ["status","input_identity","entry_number","match_type","restriction_scope","threshold","condition_text","exemptions","effective_date","legal_reference","authority_level","interpretation_note"], data.annex_xvii_results, "All matches are potential restriction matches; conditions, use, exemptions and legal text require review.");
await book("annex_vi_results.xlsx", "CLP Annex VI harmonised evidence", ["status","match_type","input_identity",{label:"index_number",get:r=>r.entry?.index_number||""},{label:"chemical_name",get:r=>r.entry?.chemical_name||""},{label:"covered_hazards",get:r=>r.covered_hazards},{label:"SCLs",get:r=>r.specific_concentration_limits},{label:"ATEs",get:r=>r.acute_toxicity_estimates},{label:"notes",get:r=>r.notes},{label:"ATP_or_act",get:r=>r.entry?.atp_or_amending_act||""},{label:"application_date",get:r=>r.entry?.application_date||""},{label:"legal_reference",get:r=>r.entry?.legal_reference||""},{label:"interpretation_note",get:r=>r.interpretation_note}], data.annex_vi_results, "Harmonised entries cover only listed hazards. Other hazard classes may require separate classification.");
const mixRows = data.mixture_calculation.calculation_trace.map(r=>({...r, calculated_mixture_ate:data.mixture_calculation.calculated_mixture_ate, resulting_category:data.mixture_calculation.resulting_category, result:data.mixture_calculation.result, rule_version:data.mixture_calculation.rule_version, legal_reference:data.mixture_calculation.source_reference}));
await book("mixture_calculation_trace.xlsx", "Acute toxicity — oral calculation trace", ["component_name","concentration","oral_ate","ate_unit","ate_source","contribution","included","decision","scenario","calculated_mixture_ate","resulting_category","result","rule_version","legal_reference"], mixRows, "Oral pilot only. The calculation is provisional where required evidence is missing; it does not make a general safety determination.");
const sdsRows = [...Object.entries(data.sds_sections).map(([section,text])=>({section,text,severity:"SUPPLIED TEXT"})), ...data.sds_review];
await book("sds_consistency_review.xlsx", "SDS consistency review", ["section","severity","text","finding","source_reference","interpretation"], sdsRows, "Synthetic SDS text reviewed for consistency. Findings do not determine that an SDS is legally invalid.");
await book("manual_review_queue.xlsx", "Manual review queue", ["module","component","status","reason","dataset_id"], data.manual_review_queue, "Review items are evidence gaps or conditional issues. They are not compliance conclusions.");
await book("source_register.xlsx", "Source register", ["dataset_id","source_name","authority_level","version","effective_date","record_count","url","checksum","reuse"], data.source_register, "Pinned curated records and legal references. ECHA bulk data was not scraped or redistributed.");
