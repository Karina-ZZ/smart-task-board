/**
 * Feature: Creator step 2 - confirm task-level facts.
 * Responsibilities: show source text, AI clarification, real draft persistence, people/performance sheets.
 * Does not own: sending, acceptance, node creation, or decomposition.
 * Plan task: WECHAT-MP-06 / FR-07.
 */
const api = require("../../utils/api");
const router = require("../../utils/router");

function localParts(value, fallbackDate, fallbackTime) {
  const text = String(value || "");
  return [text.slice(0, 10) || fallbackDate, text.slice(11, 16) || fallbackTime];
}
function today() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; }

Page({
  data: {
    draft: {}, users: [], filteredUsers: [], assigneeName:"请选择", reportToName:"请选择", reviewerName:"请选择", collaboratorDisplay:[],
    startDate: today(), startClock: "09:00", deadlineDate: "2026-09-08", deadlineClock: "18:00",
    weightOptions: [1,2,3,4,5], reportOptions: ["每周"],
    aiQuestions: [], needsClarification: false, clarificationText: "", clarifying: false, confidenceLabel: "",
    peopleSheet: false, peopleField: "", peopleTitle: "", peopleKeyword: "",
    metricSheet: false, metricMatches: [], metricLoading: false,
    saving: false,
  },
  onLoad() {
    Promise.all([api.creationDraft(), api.users()]).then(([draft, users]) => this.applyDraft(draft, users)).catch((error) => this.fail(error, "任务信息加载失败"));
  },
  applyDraft(draft, users = this.data.users) {
    const safe = { collaboratorEmployeeNos: [], reportCycle: "每周", isUrgent: false, ...draft };
    const [startDate,startClock] = localParts(safe.startTime, this.data.startDate, this.data.startClock);
    const [deadlineDate,deadlineClock] = localParts(safe.deadline, this.data.deadlineDate, this.data.deadlineClock);
    const questions=safe.confirmQuestions||[]; const score=Number(safe.confidenceScore);
    const decorated=users.map((u)=>({...u,avatar:String(u.name||u.employeeNo).slice(-1)}));
    const name=(no)=>decorated.find((u)=>u.employeeNo===no)?.name||"请选择";
    this.setData({ draft:safe, users:decorated, filteredUsers:decorated, assigneeName:name(safe.mainAssigneeEmployeeNo), reportToName:name(safe.reportToEmployeeNo), reviewerName:name(safe.reviewerEmployeeNo), collaboratorDisplay:(safe.collaboratorEmployeeNos||[]).map((employeeNo)=>({employeeNo,name:name(employeeNo)})), startDate,startClock,deadlineDate,deadlineClock, aiQuestions:questions,
      needsClarification:Boolean(questions.length||safe.missingFields?.length||safe.lowConfidenceFields?.length),
      confidenceLabel:Number.isFinite(score)&&score>0?`AI置信度 ${Math.round(score*100)}%`:"" });
  },
  fail(error, fallback) { wx.showToast({ title:error?.message||fallback, icon:"none" }); },
  back() { wx.navigateBack(); },
  editSource() { router.replace("/pages/workbench/index"); },
  input(event) { this.setData({ [`draft.${event.currentTarget.dataset.field}`]:event.detail.value }); },
  inputClarification(event) { this.setData({ clarificationText:event.detail.value }); },
  clarify() {
    const answer=this.data.clarificationText.trim(); if(!answer){this.fail(null,"请先回答AI追问");return;}
    this.setData({clarifying:true}); wx.showLoading({title:"AI继续整理"});
    api.clarifyTaskDraft(answer).then((draft)=>{wx.hideLoading();this.setData({clarifying:false,clarificationText:""});this.applyDraft(draft);wx.showToast({title:"识别结果已更新",icon:"success"});})
      .catch((e)=>{wx.hideLoading();this.setData({clarifying:false});this.fail(e,"追问失败，请重试");});
  },
  resolveAiField(field) {
    const draft = this.data.draft || {};
    const missingFields = (draft.missingFields || []).filter((item) => item !== field);
    const lowConfidenceFields = (draft.lowConfidenceFields || []).filter((item) => item !== field);
    const labels = { mainAssigneeEmployeeNo: "主承办", reportToEmployeeNo: "汇报", reviewerEmployeeNo: "验收", collaboratorEmployeeNos: "协同" };
    const confirmQuestions = (draft.confirmQuestions || []).filter((item) => {
      const text = typeof item === "string" ? item : (item?.question || "");
      return !String(text).includes(labels[field] || field);
    });
    this.setData({
      "draft.missingFields": missingFields,
      "draft.lowConfidenceFields": lowConfidenceFields,
      "draft.confirmQuestions": confirmQuestions,
      aiQuestions: confirmQuestions,
      needsClarification: Boolean(missingFields.length || lowConfidenceFields.length || confirmQuestions.length),
    });
  },
  openPeople(event) {
    const field=event.currentTarget.dataset.field; const titles={mainAssigneeEmployeeNo:"选择主承办人",reportToEmployeeNo:"选择汇报对象",reviewerEmployeeNo:"选择验收人",collaboratorEmployeeNos:"添加协同人"};
    this.setData({peopleSheet:true,peopleField:field,peopleTitle:titles[field],peopleKeyword:"",filteredUsers:this.data.users});
  },
  closePeople(){this.setData({peopleSheet:false});},
  searchPeople(event){const q=String(event.detail.value||"").trim().toLowerCase();this.setData({peopleKeyword:q,filteredUsers:this.data.users.filter((u)=>`${u.name}${u.employeeNo}`.toLowerCase().includes(q))});},
  selectPerson(event){
    const employeeNo=event.currentTarget.dataset.employee; const field=this.data.peopleField;
    if(field==="collaboratorEmployeeNos"){
      const list=[...new Set([...(this.data.draft.collaboratorEmployeeNos||[]),employeeNo])]; this.setData({"draft.collaboratorEmployeeNos":list,collaboratorDisplay:list.map((no)=>({employeeNo:no,name:this.data.users.find((u)=>u.employeeNo===no)?.name||no}))});
    } else { const name=this.data.users.find((u)=>u.employeeNo===employeeNo)?.name||employeeNo; const key=field==="mainAssigneeEmployeeNo"?"assigneeName":field==="reportToEmployeeNo"?"reportToName":"reviewerName"; this.setData({[`draft.${field}`]:employeeNo,[key]:name}); }
    this.resolveAiField(field);
    this.closePeople();
  },
  removeCollaborator(event){const no=event.currentTarget.dataset.employee;const list=(this.data.draft.collaboratorEmployeeNos||[]).filter((item)=>item!==no);this.setData({"draft.collaboratorEmployeeNos":list,collaboratorDisplay:list.map((employeeNo)=>({employeeNo,name:this.data.users.find((u)=>u.employeeNo===employeeNo)?.name||employeeNo}))});},
  noop(){},
  chooseStartDate(e){this.setData({startDate:e.detail.value});}, chooseStartTime(e){this.setData({startClock:e.detail.value});},
  chooseDeadlineDate(e){this.setData({deadlineDate:e.detail.value});}, chooseDeadlineTime(e){this.setData({deadlineClock:e.detail.value});},
  chooseWeight(e){this.setData({"draft.taskWeight":Number(e.currentTarget.dataset.value)});},
  toggleUrgent(e){this.setData({"draft.isUrgent":e.detail.value});},
  normalizedDraft(){return {...this.data.draft,startTime:`${this.data.startDate}T${this.data.startClock}:00+08:00`,deadline:`${this.data.deadlineDate}T${this.data.deadlineClock}:00+08:00`,reportCycle:"每周"};},
  validate(draft){
    if(this.data.needsClarification){this.fail(null,"请先完成AI待确认问题");return false;}
    const required=[draft.taskName,draft.taskDescription,draft.taskGoal,draft.taskSource,draft.mainAssigneeEmployeeNo,draft.reportToEmployeeNo,draft.reviewerEmployeeNo,draft.startTime,draft.deadline,draft.taskWeight];
    if(required.some((v)=>v===null||v===undefined||String(v).trim()==="")){this.fail(null,"请补齐所有必填信息");return false;}
    if(new Date(draft.deadline)<new Date(draft.startTime)){this.fail(null,"截止时间不能早于开始时间");return false;}
    return true;
  },
  saveDraft(showToast=true){
    if(this.data.saving)return Promise.reject(new Error("正在保存")); this.setData({saving:true});
    return api.saveTaskDraft(this.normalizedDraft()).then((saved)=>{this.setData({saving:false});this.applyDraft(saved);if(showToast)wx.showToast({title:"草稿已保存",icon:"success"});return saved;}).catch((e)=>{this.setData({saving:false});this.fail(e,"草稿保存失败");throw e;});
  },
  openMetrics(){
    this.saveDraft(false).then((saved)=>{this.setData({metricSheet:true,metricLoading:true});return api.performanceMatches(saved.taskId, saved.taskVersion);})
      .then((matches)=>this.setData({metricMatches:matches,metricLoading:false})).catch(()=>this.setData({metricLoading:false}));
  },
  closeMetrics(){this.setData({metricSheet:false});},
  chooseNoMetric(){
    const draft=this.data.draft;
    const clear=draft.taskId ? api.clearPerformanceMatch(draft.taskId, draft.taskVersion) : Promise.resolve();
    clear.then(()=>{this.setData({"draft.performanceMetricId":null,"draft.performanceMetric":"不关联绩效",metricSheet:false});return api.saveCreationDraft(this.data.draft);})
      .then(()=>wx.showToast({title:"已设置为不关联绩效",icon:"success"})).catch((e)=>this.fail(e,"取消绩效关联失败"));
  },
  selectMetric(event){
    const matchId=event.currentTarget.dataset.match; const match=this.data.metricMatches.find((m)=>m.performanceMatchId===matchId); if(!match)return;
    api.confirmPerformanceMatch(this.data.draft.taskId, matchId, this.data.draft.taskVersion).then(()=>{this.setData({"draft.performanceMetricId":match.metricId,"draft.performanceMetric":match.metricName,metricSheet:false});return api.saveCreationDraft(this.data.draft);}).then(()=>wx.showToast({title:"绩效指标已确认",icon:"success"})).catch((e)=>this.fail(e,"绩效确认失败"));
  },
  next(){const draft=this.normalizedDraft();if(!this.validate(draft))return;this.saveDraft(false).then(()=>router.go("/pages/create-confirm/index")).catch(()=>{});},
});
