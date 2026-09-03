/** Feature 06 acceptance: three-step creator flow, notification isolation, no creator nodes. */
const assert=require("node:assert/strict");
let storage={};
global.wx={getStorageSync:(k)=>storage[k],setStorageSync:(k,v)=>{storage[k]=JSON.parse(JSON.stringify(v));},removeStorageSync:(k)=>{delete storage[k];}};
const store=require("../utils/store");
store.reset(); store.switchUser("E1003");
const saved=store.saveTaskDraft({taskName:"功能06串联验收",taskDescription:"验证三步创建和通知隔离",taskGoal:"发送后仅待接受",taskSource:"功能测试",mainAssigneeEmployeeNo:"E1001",reportToEmployeeNo:"E1003",reviewerEmployeeNo:"E1003",collaboratorEmployeeNos:["E1002"],startTime:"2026-09-02T09:00:00+08:00",deadline:"2026-09-10T18:00:00+08:00",taskWeight:4,reportCycle:"每周",acceptanceCriteria:"主承办人收到且无节点"});
let state=store.read(); let task=state.tasks.find((t)=>t.taskId===saved.taskId);
assert.equal(task.status,"draft"); assert.equal(state.nodes.filter((n)=>n.taskId===task.taskId).length,0); assert.equal(state.notifications.filter((n)=>n.taskId===task.taskId).length,0);
const matches=store.suggestPerformanceMatches(task.taskId); assert.ok(matches.length>0); store.confirmPerformanceMatch(task.taskId,matches[0].performanceMatchId);
const sent=store.sendTask({...saved,performanceMetricId:matches[0].metricId,performanceMetric:matches[0].metricName});
assert.equal(sent.status,"pending_accept"); assert.equal(sent.effectiveAt,null); assert.equal(sent.nodes.length,0); assert.ok(sent.taskNo);
state=store.read(); const notices=state.notifications.filter((n)=>n.taskId===sent.taskId&&n.title==="新任务待接受");
assert.equal(notices.length,1); assert.equal(notices[0].recipientEmployeeNo,"E1001");
assert.equal(store.listNotifications().some((n)=>n.taskId===sent.taskId),false,"creator must not receive assignee notice");
assert.throws(()=>store.acceptTask(sent.taskId),/STATUS_OR_PERMISSION_DENIED/);
store.switchUser("E1005"); assert.equal(store.getTask(sent.taskId).taskId,sent.taskId); assert.equal(store.listNotifications().some((n)=>n.taskId===sent.taskId),false); assert.throws(()=>store.acceptTask(sent.taskId),/STATUS_OR_PERMISSION_DENIED/);
store.switchUser("E1001"); assert.equal(store.listNotifications().filter((n)=>n.taskId===sent.taskId).length,1);
console.log("task-creation.test.js: PASS");
