const fs = require('fs');
const path = require('path');
const dir = __dirname;
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const colors = {blue:'#2563eb',green:'#087f70',orange:'#b65a12',ink:'#172a46',muted:'#556980'};
let parts=[];
function text(x,y,s,size=24,fill=colors.ink,weight=400){parts.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${esc(s)}</text>`)}
function box(x,y,w,h,title,lines,color='blue',size=24){const c=colors[color];parts.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="18" fill="white" stroke="#d9e3ef" stroke-width="2"/><rect x="${x}" y="${y}" width="8" height="${h}" rx="4" fill="${c}"/>`);text(x+25,y+43,title,29,c,700);lines.forEach((s,i)=>text(x+25,y+86+i*37,s,size));}
function arrow(x1,y1,x2,y2,color='blue',label){const c=colors[color];parts.push(`<path d="M ${x1} ${y1} L ${x2} ${y2}" fill="none" stroke="${c}" stroke-width="3" marker-end="url(#${color})"/>`);if(label)text((x1+x2)/2+12,(y1+y2)/2-12,label,21,c,600)}
function start(n,title,sub){parts=[];parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-label="${esc(title)}"><defs>${Object.entries(colors).map(([k,c])=>`<marker id="${k}" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="${c}"/></marker>`).join('')}</defs><rect width="1600" height="900" fill="#f3f6fb"/><g font-family="Microsoft YaHei, PingFang SC, sans-serif">`);text(60,49,`GENB · 架构讲解 / ${n}     2026-09-08 · 规划示意，尚未实施`,18,colors.muted,600);text(60,112,title,42,colors.ink,700);text(60,157,sub,23,colors.muted);}
const slides=[];
function finish(name,notes){text(60,861,'蓝色：平台与访问    绿色：智能体运行    橙色：部署管理 / 待核验事项',19,colors.muted);parts.push('</g></svg>');fs.writeFileSync(path.join(dir,name+'.svg'),parts.join('\n'));slides.push({name,notes});}

start('01','整体架构：18 接待用户，47 管理，新节点运行智能体','建议部署示例：网关鉴权服务放 47，容量与网络需上线前核验；不是当前生产拓扑。');
box(60,220,280,180,'用户 / 管理员',['登录统一门户','选择、上传、使用智能体'],'blue',22);
box(420,220,440,220,'18 · 统一前端服务器',['已有：前端页面、Nginx','调整：通用 /agents/{id}/ 入口','负责：检查访问权限、转发请求'],'blue',23);
box(990,220,550,220,'新服务器 B / C · 运行节点',['安装：Docker、SSH/SFTP 服务','部署：受控操作工具、智能体容器','提供：健康检查、状态、日志'],'green',24);
box(420,555,550,235,'47 · 管理中心 + 既有运行节点',['更新：GenB 后端 JAR、部署任务','新增：网关鉴权服务、专用 Redis','保留：PostgreSQL、既有智能体','管理：节点、权限、材料、路由版本'],'blue',23);
box(1060,580,480,185,'两条链路分别连通',['使用：18 → 目标智能体业务端口','部署：47 → 节点受控 SSH/SFTP','47 本机智能体也可作为访问目标'],'orange',22);
arrow(340,305,420,305);arrow(860,305,990,305,'green');text(886,276,'业务流',20,colors.green);
arrow(620,440,620,555,'blue');text(644,498,'管理操作 / 权限检查',21,colors.blue);
parts.push('<path d="M970 676 L1016 676 L1016 479 L1260 479 L1260 440" fill="none" stroke="#b65a12" stroke-width="3" marker-end="url(#orange)"/>');text(1050,522,'部署文件与操作',21,colors.orange);
finish('01-整体架构', ["这次改造后，用户仍然从同一个平台登录和使用智能体。变化发生在后台：47 负责统一管理，新增服务器负责运行智能体，18 上的 Nginx 继续作为访问入口。47 也可以继续运行现有智能体。","管理员部署智能体时，由 47 把文件和操作发送到所选服务器。用户使用智能体时，18 先通过网关检查权限，再把请求转发给实际运行它的服务器。部署管理和用户访问是两条不同的链路，都需要打通。","这样，增加服务器后，智能体可以分散运行，用户不用记住不同的 IP 和端口。图中网关服务暂按放在 47 规划，实施前要确认资源是否够用；18 的入口带宽也需要一并评估。"]);

start('02','每台服务器：装什么软件，部署什么程序','“安装软件”是准备运行环境；“部署代码”是发布本项目的程序和配置。');
box(60,210,465,495,'47 · 更新管理能力',['已有环境（实施前核验）','• Java 17：运行 GenB 后端','• PostgreSQL、Redis、Docker','拟新增 / 配置','• SSH/SFTP 客户端或 Java 库','• 部署文件目录、任务记录','拟部署','• 更新后的 GenB JAR','• 网关应用 + 隔离专用 Redis','• 本机节点受控操作工具'],'blue',22);
box(560,210,465,495,'新节点 · 准备执行环境',['基础软件','• Linux + Docker Engine','• SSH 服务及 SFTP 子系统','• 文件完整性、空间检查工具','拟配置 / 部署','• 专用账号、受控操作工具','• 部署目录、日志与资源限额','• 上传导入的智能体镜像/容器','按智能体实际需要','• 持久卷；GPU 驱动仅按需'],'green',22);
box(1060,210,480,495,'18 · 保持统一入口',['已有环境（实施前核验）','• Nginx + 静态前端产物','拟部署 / 调整','• 更新中英文管理端、客户端','• 配置通用智能体代理规则','• 正式入口域名及 HTTPS','• 到网关和各运行节点的连通','职责边界','• 默认不运行智能体容器','• 不安装 GenB JAR/数据库'],'blue',22);
box(60,732,1480,80,'运行时说明',[''], 'orange');
text(305,782,'网关容器内携带 Python 3.11+；新节点通常无需另装 Java/Python/Node.js，依赖由智能体镜像携带。',21,colors.ink);
finish('02-软件与部署清单', ["47 主要升级现有 GenB 后端，增加服务器管理、远程部署和任务记录。数据库保存“哪个智能体部署在哪里、部署到哪一步”；拟新增的网关服务检查访问权限，专用 Redis 保存网关会话和缓存，减少重复查询。","新服务器主要准备 Docker 和 SSH。Docker 运行智能体，SSH/SFTP 让 47 安全地发送文件、启动或停止指定容器。还需要配置专用账号、部署目录和操作权限。智能体依赖的 Python、Java 等通常随镜像打包，新节点不必再装一整套 GenB 平台。","18 继续运行 Nginx 和平台页面，更新页面功能并配置统一访问规则和 HTTPS。新节点的 GPU、持久化数据目录等按智能体需要准备，不是每台都要安装。首版由 47 主动下发操作，新节点不用额外运行一个常驻的任务领取服务。"]);

start('03','一次完整交付：上传 → 选节点 → 运行 → 发布','管理员在一个页面完成操作；平台把每个阶段的进度和失败原因显示出来。');
box(60,225,440,205,'① 上传并选择服务器',['上传 OAG Docker 镜像归档','选择：47 / 已接入新节点 B','后端保存材料、任务与校验值'],'blue',23);
box(580,225,440,205,'② 47 分发并发起操作',['检查目标节点资源、权限和端口','安全传输 → 检查文件完整性','发起受控导入和启动操作'],'orange',23);
box(1100,225,440,205,'③ 新节点运行实例',['Docker 导入并启动指定镜像','返回实例归属、状态和日志','应用健康检查通过'],'green',23);
arrow(500,320,580,320,'orange');arrow(1020,320,1100,320,'orange');
box(60,540,440,205,'⑥ 用户从固定入口访问',['https://实际域名/agents/oag/','网关鉴权后定位实例','迁移运行节点，入口保持不变'],'blue',23);
box(580,540,440,205,'⑤ 网关应用新版本',['加载端点授权和路由配置','检查后整体更新并回报结果','正常新增无需重启网关'],'blue',23);
box(1100,540,440,205,'④ 管理员检查并发布',['启动成功 ≠ 已经对用户开放','确认权限与接入兼容性','47 生成新的配置版本'],'orange',23);
arrow(1320,430,1320,540,'green');arrow(1100,645,1020,645);arrow(580,645,500,645);
text(60,799,'异常处理：失败停在当前阶段；超时先核对远端结果，避免重复容器；新版本失败不停止原实例。',24,colors.orange,600);
finish('03-上传部署与发布流程', ["以 OAG 为例，管理员上传打包好的 Docker 镜像，选择部署到 47 还是新服务器 B。平台先检查权限、空间和端口，再把文件发送过去，并核对文件是否完整。管理员可以看到分发、导入、启动和检查的进度。","容器启动后，还要检查 OAG 是否真的能正常响应。检查通过，管理员再点击发布，平台才把它加入统一访问入口。上传成功、运行成功和发布成功是三个不同状态，页面会分别展示。","用户最终通过固定域名下的 /agents/oag/ 使用它。如果将来搬到其他服务器，只调整内部目标；已有文件和业务数据需要配套迁移。新版本部署失败时保留原服务，超时先查清远端结果，避免重复启动。"]);

start('04','新增智能体：增加一条记录，网关自动认识它','网关保存通用规则；GenB 维护并发布“智能体 → 运行实例”的通讯录。');
box(60,230,500,290,'47 · GenB 发布配置',['版本 100：OAG → 节点 A:8052','版本 101：新增审单 → 节点 B:8060','版本 102：OAG 改到节点 C:8052','','配置含：智能体、端点、身份模式','独立权限体系仍检查谁可以访问'],'blue',23);
box(660,230,390,290,'网关 · 自动更新',['发现新版本','验证目标节点获准访问','整体应用路由表','回报已应用版本','','无需为每个智能体写代码'],'blue',23);
box(1150,230,390,290,'Nginx · 通用代理',['匹配 /agents/{agentId}/','向网关查询访问决定','转发到获准目标','','OAG、审单共用同一规则','不逐个增加 location'],'green',23);
arrow(560,375,660,375);arrow(1050,375,1150,375);
box(60,585,1480,195,'现有代码必须先补齐的三点',['① 普通智能体可以独立发布，不要求先绑定记忆、推理等核心组件。','② 允许接入的服务器地址可以动态更新，但必须先经过授权和检查。','③ 用户入口与实际运行地址分开，确认网关已更新后才显示发布生效。'],'orange',24);
finish('04-动态接入原理', ["网关可以理解为按通讯录转接的前台。通讯录记录“OAG 在哪台服务器、使用哪个端口”。新增一个智能体，就是增加一条已审核的记录；迁移服务器，就是更新这条记录。","GenB 每次发布都会生成新的配置版本。网关发现更新后，检查目标服务器是否允许接入，再整体加载并回报结果。Nginx 使用同一套通用规则转发请求，因此符合接入规范的新智能体通常不需要修改网关代码或重启网关。","现在要补齐三件事：普通智能体可以独立发布；新增服务器地址可以受控更新；页面能确认配置已经生效。任意填写一个地址不能直接放行。遇到特殊登录方式或不兼容的页面路径，仍需单独做适配。"]);

start('05','代码改造地图：界面、后端、网关、节点执行入口','改造重点：页面能选节点，后端能远程执行，网关能自动更新，操作结果能查清。');
box(60,215,710,245,'管理端 / 客户端 → 部署到 18',['AgentDeploy.vue：选节点、上传/部署进度','AgentRuntime.vue：按实例启停、状态与日志','拟新增节点管理页；补齐中英文文案','agentLaunch.ts / clientAgents.ts：固定入口和可用状态'],'blue',24);
box(830,215,710,245,'GenB 后端 → 更新 47 上的 JAR',['部署接口：从操作本机改为操作指定节点','运行管理：启停、状态和日志对应正确实例','任务记录：保存进度，失败后可查明和恢复','数据库：关联智能体、服务器和部署版本'],'orange',23);
box(60,510,710,250,'动态配置与网关 → 拟部署到 47',['发布服务：生成智能体与运行地址的对应表','地址检查：只允许转发到获准的服务器','配置更新：自动加载新版本并反馈是否生效','回归验证：原有智能体、权限和异常恢复'],'blue',24);
box(830,510,710,250,'新节点执行入口 + 18 Nginx 配置',['节点：只接受获准的部署操作，核对目标容器','节点：接收材料、导入、启停、查询状态和日志','18：通用访问规则，支持页面和流式回答','后台不能继续默认操作本机 Docker'],'green',23);
text(60,810,'数据库增量模型：节点 → 实例 → 智能体；材料 → 部署任务；路由发布 → 网关确认。既有业务数据保留。',23,colors.ink,600);
finish('05-代码改造地图', ["代码改造分为四块。第一块是页面：上传时能选服务器，能看部署进度，也能查看指定实例的日志和执行启停。用户侧则使用固定入口，并能看到智能体是否真正可用。","第二块是 47 上的后端：把原来操作本机 Docker 的逻辑，改成先确认目标节点，再执行部署。数据库要保存服务器、运行实例、部署材料和任务结果，确保两台服务器即使端口一样，也不会查错日志或停错容器。","第三块是网关：自动加载新路由、检查获准目标并反馈生效状态。第四块是新节点上的受限执行入口，以及 18 的通用 Nginx 配置。完成后，日常新增标准智能体由管理员在页面操作，不再逐个找开发人员修改网关。"]);

const labels=['整体分工','软件与程序','部署流程','动态接入','代码改造'];
const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GenB 多节点部署方案</title><style>*{box-sizing:border-box}body{margin:0;background:#e9eef5;color:#172a46;font-family:'Microsoft YaHei',sans-serif}header{padding:25px 4%;background:#172a46;color:white}h1{margin:0 0 12px;font-size:30px}header p{line-height:1.7;font-size:19px;margin:0 0 18px;color:#d5e3f5}nav{display:flex;gap:12px;flex-wrap:wrap}nav a{padding:8px 18px;border:1px solid #8299b8;border-radius:8px;color:white;text-decoration:none;font-size:18px}main{max-width:1600px;margin:auto;padding:24px}section{margin-bottom:40px;scroll-margin-top:12px;background:white;border-radius:14px;overflow:hidden;box-shadow:0 8px 30px #172a4610}section img{display:block;width:100%;height:auto}.copy{padding:18px 44px 28px;border-top:1px solid #dce5f0;display:grid;gap:14px}.copy p{margin:0;font-size:24px;line-height:1.85;letter-spacing:.25px}.copy p:first-child{font-weight:600;color:#244b7e}footer{padding:8px 24px 28px;color:#556980;font-size:17px;line-height:1.8}@media(max-width:800px){main{padding:10px}.copy{padding:22px}.copy p{font-size:19px}}@media print{@page{size:A3 portrait;margin:10mm}header,footer{display:none}main{padding:0;max-width:none}section{break-after:page;break-inside:avoid;margin:0;box-shadow:none;border-radius:0}.copy{padding:15px 20px}.copy p{font-size:20px}body{background:white}}</style></head><body><header><h1>GenB 多节点远程部署与统一访问</h1><p>统一管理、多台服务器运行；管理员选择部署位置，用户使用固定入口。方案设计 · 2026-09-08 · 待实施</p><nav>${slides.map((s,i)=>`<a href="#s${i}">${i+1}. ${labels[i]}</a>`).join('')}</nav></header><main>${slides.map((s,i)=>`<section id="s${i}"><img src="${s.name}.svg" alt="${labels[i]}"><div class="copy">${s.notes.map(p=>`<p>${esc(p)}</p>`).join('')}</div></section>`).join('')}<footer>本方案采用 Docker 镜像部署和受控远程操作。网关服务拟放在 47，实施前核验容量、网络与权限；18 继续承担统一前端入口。</footer></main></body></html>`;
fs.writeFileSync(path.join(dir,'多节点部署讲解图册.html'),html);
console.log(JSON.stringify({slides:slides.length,output:dir}));
