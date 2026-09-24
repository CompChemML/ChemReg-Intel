import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
const root = new URL(".", import.meta.url).pathname.replace(/^\//, "");
const names = ["synthetic_formulation","identity_resolution","candidate_list_results","annex_xvii_results","annex_vi_results","mixture_calculation_trace","sds_consistency_review","manual_review_queue","source_register"];
await fs.mkdir(`${root}/renders`, {recursive:true});
for (const name of names) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(`${root}/${name}.xlsx`));
  const check = await wb.inspect({kind:"table",range:"Results!A1:N12",include:"values,formulas",tableMaxRows:12,tableMaxCols:14});
  const errors = await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:20}});
  if (errors.ndjson.includes('"matches":[]') === false && errors.ndjson.includes('matches') ) throw new Error(`${name}: formula error scan ${errors.ndjson}`);
  const image = await wb.render({sheetName:"Results",range:"A1:N12",scale:1,format:"png"});
  await fs.writeFile(`${root}/renders/${name}.png`,new Uint8Array(await image.arrayBuffer()));
  console.log(`${name}: ${check.ndjson.slice(0,180).replace(/\n/g," ")}`);
}
