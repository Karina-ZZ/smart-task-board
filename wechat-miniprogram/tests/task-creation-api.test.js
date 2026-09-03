/** Feature 06 API contract integration from Mini Program data gateway through create/send endpoints. */
const assert=require("node:assert/strict");
let storage={"wangxu.accessToken":"token"}; const calls=[]; let version=1;
global.wx={
 getStorageSync:(k)=>storage[k], setStorageSync:(k,v)=>{storage[k]=JSON.parse(JSON.stringify(v));}, removeStorageSync:(k)=>delete storage[k],
 request(o){calls.push({url:o.url,method:o.method,data:o.data,header:o.header}); const p=o.url.replace("https://task.test","");
  if(p==="/api/v1/tasks"&&o.method==="POST"){o.success({statusCode:201,data:{task_id:"11111111-1111-4111-8111-111111111111",status:"draft",task_version:version++,updated_at:"2026-09-02T10:00:00Z"}});return;}
  if(p.includes("/draft")&&o.method==="PATCH"){o.success({statusCode:200,data:{task_id:"11111111-1111-4111-8111-111111111111",status:"draft",task_version:version++,updated_at:"2026-09-02T10:01:00Z"}});return;}
  if(p.includes("submit-for-confirmation")){o.success({statusCode:200,data:{task_id:"11111111-1111-4111-8111-111111111111",status:"pending_confirmation",task_version:version++,updated_at:"2026-09-02T10:02:00Z"}});return;}
  if(p.includes("confirm-and-send")){o.success({statusCode:200,data:{task_id:"11111111-1111-4111-8111-111111111111",status:"pending_acceptance",task_version:version++,updated_at:"2026-09-02T10:03:00Z"}});return;}
  throw new Error(`unexpected ${o.method} ${p}`);
 }
};
const config=require("../config"); config.mode="api"; config.apiBaseUrl="https://task.test";
const api=require("../utils/api");
(async()=>{
 const draft={taskName:"API联通",taskDescription:"真实草稿",taskGoal:"待接受",taskSource:"测试",mainAssigneeEmployeeNo:"E1001",reportToEmployeeNo:"E1003",reviewerEmployeeNo:"E1003",collaboratorEmployeeNos:["E1002"],startTime:"2026-09-02T09:00:00+08:00",deadline:"2026-09-10T18:00:00+08:00",taskWeight:4,acceptanceCriteria:"无节点"};
 const saved=await api.saveTaskDraft(draft); assert.equal(saved.taskId,"11111111-1111-4111-8111-111111111111"); assert.equal(saved.backendStatus,"draft");
 const sent=await api.sendTask(saved); assert.equal(sent.status,"pending_acceptance");
 const create=calls.find((x)=>x.method==="POST"&&x.url.endsWith("/api/v1/tasks")); assert.ok(create); assert.equal(create.data.task_name,"API联通"); assert.equal(create.data.nodes,undefined); assert.equal(create.data.estimated_hours,undefined);
 const confirm=calls.find((x)=>x.url.includes("confirm-and-send")); assert.match(confirm.header["Idempotency-Key"],/^confirm-/);
 console.log("task-creation-api.test.js: PASS");
})().catch((e)=>{console.error(e);process.exitCode=1;});
