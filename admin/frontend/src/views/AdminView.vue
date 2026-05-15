<template>
  <div class="admin-shell">
    <aside class="sidebar">
      <div class="brand">
        <p class="eyebrow">BOU Admin</p>
        <h1>智能客服管理后台</h1>
      </div>
      <nav class="nav">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="nav-button"
          :class="{ active: activeTab === item.key }"
          @click="activeTab = item.key"
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>
      </nav>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <p class="eyebrow">{{ currentSection.subtitle }}</p>
          <h2>{{ currentSection.title }}</h2>
        </div>
        <span class="tag">MVP 演示环境</span>
      </header>

      <section v-if="activeTab === 'kb'" class="page stack">
        <div class="subtabs">
          <button class="subtab" :class="{ active: kbTab === 'build' }" @click="kbTab = 'build'">导入构建</button>
          <button class="subtab" :class="{ active: kbTab === 'documents' }" @click="kbTab = 'documents'">文档列表</button>
          <button class="subtab" :class="{ active: kbTab === 'recall' }" @click="kbTab = 'recall'">召回测试</button>
        </div>

        <div v-if="kbTab === 'build'" class="grid-two">
          <section class="panel">
            <div class="panel-header">
              <div>
                <h3>知识文档导入</h3>
                <p class="muted">支持飞书链接、本地文本文件和手动粘贴，统一进入元数据与分块流程。</p>
              </div>
              <div class="header-actions">
                <button class="btn" :disabled="loading.upload" @click="triggerFileUpload">
                  {{ loading.upload ? '上传中' : '上传文件' }}
                </button>
                <button class="btn primary" :disabled="loading.fetch || !feishuUrl.trim()" @click="fetchFeishu">
                  {{ loading.fetch ? '拉取中' : '拉取文档' }}
                </button>
              </div>
            </div>

            <div class="panel-body stack">
              <input ref="fileInputRef" type="file" accept=".md,.markdown,.txt,.json,.csv,.tsv,.log" style="display: none" @change="handleFileUpload" />

              <label class="field">
                <span>飞书文档链接</span>
                <input v-model="feishuUrl" class="input" placeholder="https://my.feishu.cn/wiki/..." />
              </label>

              <div class="grid-form">
                <label class="field">
                  <span>文档标题</span>
                  <input v-model="draft.title" class="input" />
                </label>
                <label class="field">
                  <span>知识分类</span>
                  <select v-model="draft.metadata.category" class="select">
                    <option>产品功能</option>
                    <option>会员权益</option>
                    <option>活动规则</option>
                    <option>角色介绍</option>
                    <option>故障说明</option>
                    <option>聊天质量</option>
                  </select>
                </label>
                <label class="field">
                  <span>负责人</span>
                  <input v-model="draft.metadata.owner" class="input" />
                </label>
                <label class="field">
                  <span>版本</span>
                  <input v-model="draft.metadata.version" class="input" />
                </label>
                <label class="field">
                  <span>状态</span>
                  <select v-model="draft.metadata.status" class="select">
                    <option value="draft">草稿</option>
                    <option value="reviewing">待审核</option>
                    <option value="published">已发布</option>
                    <option value="archived">已下线</option>
                  </select>
                </label>
                <label class="field">
                  <span>标签</span>
                  <input v-model="tagInput" class="input" placeholder="用逗号分隔，如 高频问题,飞书同步" />
                </label>
              </div>

              <div class="grid-strategy">
                <label class="field">
                  <span>分块策略</span>
                  <select v-model="draft.strategy.method" class="select">
                    <option value="heading">按标题结构</option>
                    <option value="semantic">按段落语义</option>
                    <option value="fixed">固定长度</option>
                  </select>
                </label>
                <label class="field">
                  <span>Chunk 大小</span>
                  <input v-model.number="draft.strategy.chunk_size" type="number" min="120" max="3000" class="input" />
                </label>
                <label class="field">
                  <span>Overlap</span>
                  <input v-model.number="draft.strategy.overlap" type="number" min="0" max="800" class="input" />
                </label>
                <button class="btn" :disabled="loading.preview || !draft.content.trim()" @click="previewChunks">
                  {{ loading.preview ? '生成中' : '预览分块' }}
                </button>
              </div>

              <label class="field">
                <span>文档正文</span>
                <textarea v-model="draft.content" class="textarea" placeholder="拉取飞书后会自动填充，也可以手动粘贴 Markdown 文档。" />
              </label>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <div>
                <h3>Chunk 预览</h3>
                <p class="muted">{{ chunkSummaryText }}</p>
              </div>
              <button class="btn success" :disabled="loading.save || !chunks.length" @click="saveDocument">
                {{ loading.save ? '保存中' : '保存草稿' }}
              </button>
            </div>
            <div class="chunk-list">
              <article v-for="chunk in chunks" :key="chunk.chunk_id" class="chunk">
                <div class="chunk-head">
                  <span>#{{ chunk.index + 1 }} {{ chunk.title_path || '正文片段' }}</span>
                  <span>{{ chunk.token_estimate }} tokens</span>
                </div>
                <p class="chunk-content">{{ chunk.content }}</p>
              </article>
              <div v-if="!chunks.length" class="empty">还没有 chunk。先拉取文档或粘贴正文，然后点击预览分块。</div>
            </div>
          </section>
        </div>

        <section v-if="kbTab === 'documents'" class="panel">
          <div class="panel-header">
            <div>
              <h3>知识文档列表</h3>
              <p class="muted">飞书来源可立即同步；内容变更后进入待审核，确认无误后发布。</p>
            </div>
            <button class="btn" @click="loadDocuments">刷新</button>
          </div>
          <div v-if="saveNotice" class="notice">{{ saveNotice }}</div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>分类</th>
                  <th>状态</th>
                  <th>分块</th>
                  <th>负责人</th>
                  <th>同步</th>
                  <th>更新时间</th>
                  <th>发布流程</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in documents" :key="doc.doc_id">
                  <td class="strong">{{ doc.title }}</td>
                  <td>{{ doc.metadata?.category }}</td>
                  <td><StatusPill :status="doc.metadata?.status" /></td>
                  <td>{{ doc.chunk_count }}</td>
                  <td>{{ doc.metadata?.owner }}</td>
                  <td>
                    <div class="sync-cell">
                      <span>{{ sourceLabel(doc.source_type) }}</span>
                      <span>{{ syncStatusLabel(doc.last_sync_status) }}</span>
                      <span v-if="doc.last_sync_at">上次：{{ formatDate(doc.last_sync_at) }}</span>
                      <select
                        :value="doc.sync_config?.sync_frequency || 'manual'"
                        :disabled="doc.source_type !== 'feishu'"
                        class="mini-select"
                        @change="updateSyncConfig(doc, { sync_frequency: $event.target.value })"
                      >
                        <option value="manual">手动</option>
                        <option value="hourly">每小时</option>
                        <option value="daily">每天</option>
                        <option value="weekly">每周</option>
                      </select>
                      <label class="mini-check">
                        <input
                          type="checkbox"
                          :checked="Boolean(doc.sync_config?.sync_enabled)"
                          :disabled="doc.source_type !== 'feishu'"
                          @change="updateSyncConfig(doc, { sync_enabled: $event.target.checked })"
                        />
                        自动同步
                      </label>
                      <label class="mini-check">
                        <input
                          type="checkbox"
                          :checked="Boolean(doc.sync_config?.auto_publish)"
                          :disabled="doc.source_type !== 'feishu'"
                          @change="updateSyncConfig(doc, { auto_publish: $event.target.checked })"
                        />
                        自动发布
                      </label>
                    </div>
                  </td>
                  <td>{{ formatDate(doc.updated_at) }}</td>
                  <td>
                    <div class="row-actions">
                      <button class="mini-btn" :disabled="doc.source_type !== 'feishu' || syncingDocId === doc.doc_id" @click="syncNow(doc)">
                        {{ syncingDocId === doc.doc_id ? '同步中' : '立即同步' }}
                      </button>
                      <button class="mini-btn" :disabled="doc.metadata?.status === 'reviewing'" @click="updateDocumentStatus(doc, 'reviewing')">提交审核</button>
                      <button class="mini-btn success" :disabled="doc.metadata?.status === 'published'" @click="updateDocumentStatus(doc, 'published')">发布</button>
                      <button class="mini-btn" :disabled="doc.metadata?.status === 'archived'" @click="updateDocumentStatus(doc, 'archived')">下线</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!documents.length">
                  <td colspan="7" class="empty">暂无保存的知识文档。</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="kbTab === 'recall'" class="panel">
          <div class="panel-header">
            <div>
              <h3>召回测试</h3>
              <p class="muted">输入真实用户问题，检查已发布知识能否召回正确 chunk。</p>
            </div>
            <button class="btn primary" :disabled="loading.recall || !recallForm.query.trim()" @click="runRecallTest">
              {{ loading.recall ? '测试中' : '运行测试' }}
            </button>
          </div>
          <div class="panel-body stack">
            <div class="recall-form">
              <label class="field">
                <span>测试 Query</span>
                <input v-model="recallForm.query" class="input" placeholder="例如：聊天里出现红色感叹号是怎么回事？" />
              </label>
              <label class="field">
                <span>知识状态</span>
                <select v-model="recallForm.status_filter" class="select">
                  <option value="published">只测已发布</option>
                  <option value="reviewing">只测待审核</option>
                  <option value="draft">只测草稿</option>
                  <option value="all">全部状态</option>
                </select>
              </label>
              <label class="field">
                <span>Top K</span>
                <input v-model.number="recallForm.top_k" class="input" type="number" min="1" max="20" />
              </label>
            </div>

            <div v-if="recallSummary" class="recall-summary">
              候选命中 {{ recallSummary.candidate_count }} 个，返回 {{ recallSummary.returned_count }} 个，过滤状态：{{ recallStatusLabel(recallSummary.status_filter) }}
            </div>

            <div class="recall-results">
              <article v-for="hit in recallResults" :key="hit.chunk_id" class="recall-hit">
                <div class="recall-hit-head">
                  <div>
                    <strong>{{ hit.document_title }}</strong>
                    <p>{{ hit.title_path || '正文片段' }} · {{ hit.metadata?.category }} · {{ statusLabel(hit.metadata?.status) }}</p>
                  </div>
                  <span class="score">{{ hit.score }}</span>
                </div>
                <p class="chunk-content">{{ hit.content }}</p>
                <div class="hit-debug">
                  命中词：{{ hit.scoring?.keyword_hits?.length ? hit.scoring.keyword_hits.join('、') : '无' }}
                  ｜overlap：{{ hit.scoring?.semantic_overlap }}
                  ｜title：{{ hit.scoring?.title_boost }}
                </div>
              </article>
              <div v-if="recallSearched && !recallResults.length" class="empty">没有召回结果。可以检查知识状态、分块策略、相似问或元数据。</div>
            </div>
          </div>
        </section>
      </section>

      <section v-if="activeTab === 'eval'" class="page stack">
        <div class="eval-grid">
          <section class="panel">
            <div class="panel-header">
              <div>
                <h3>评测集管理</h3>
                <p class="muted">维护用户问题、标准答案、期望文档或 chunk，用于自动化回归。</p>
              </div>
              <button class="btn" @click="loadEvaluationCases">刷新</button>
            </div>
            <div class="panel-body stack">
              <div class="grid-form">
                <label class="field">
                  <span>用户问题</span>
                  <input v-model="evalCaseForm.question" class="input" placeholder="例如：聊天里出现红色感叹号是怎么回事？" />
                </label>
                <label class="field">
                  <span>期望意图</span>
                  <input v-model="evalCaseForm.expected_intent" class="input" placeholder="usage_issue / product_info" />
                </label>
              </div>
              <label class="field">
                <span>标准答案 / 期望口径</span>
                <textarea v-model="evalCaseForm.expected_answer" class="textarea compact-textarea" placeholder="用于人工评测或后续 LLM-as-Judge。" />
              </label>
              <div class="grid-form">
                <label class="field">
                  <span>期望文档 ID</span>
                  <input v-model="evalCaseForm.expected_doc_id" class="input" placeholder="可选，不填则只做辅助召回判断" />
                </label>
                <label class="field">
                  <span>期望 Chunk IDs</span>
                  <input v-model="expectedChunkInput" class="input" placeholder="可选，用逗号分隔" />
                </label>
              </div>
              <button class="btn primary" :disabled="!evalCaseForm.question.trim()" @click="createEvaluationCase">新增评测用例</button>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <div>
                <h3>自动化运行</h3>
                <p class="muted">第一版聚焦 RAG 召回评测：Recall@K、MRR、BadCase。</p>
              </div>
              <button class="btn primary" :disabled="loading.evalRun" @click="runEvaluation">
                {{ loading.evalRun ? '运行中' : '运行评测' }}
              </button>
            </div>
            <div class="panel-body stack">
              <div class="grid-form">
                <label class="field">
                  <span>知识状态</span>
                  <select v-model="evalRunForm.status_filter" class="select">
                    <option value="published">只测已发布</option>
                    <option value="reviewing">只测待审核</option>
                    <option value="draft">只测草稿</option>
                    <option value="all">全部状态</option>
                  </select>
                </label>
                <label class="field">
                  <span>Top K</span>
                  <input v-model.number="evalRunForm.top_k" class="input" type="number" min="1" max="20" />
                </label>
              </div>

              <div v-if="latestRun" class="metric-grid">
                <div class="metric-card">
                  <span>Recall@K</span>
                  <strong>{{ percent(latestRun.metrics.recall_at_k) }}</strong>
                </div>
                <div class="metric-card">
                  <span>MRR</span>
                  <strong>{{ latestRun.metrics.mrr }}</strong>
                </div>
                <div class="metric-card">
                  <span>BadCase</span>
                  <strong>{{ latestRun.metrics.badcase_count }}</strong>
                </div>
                <div class="metric-card">
                  <span>平均 Top 分</span>
                  <strong>{{ latestRun.metrics.avg_top_score }}</strong>
                </div>
              </div>

              <div v-if="!latestRun" class="empty">还没有运行报告。点击“运行评测”生成第一份报告。</div>
            </div>
          </section>
        </div>

        <section class="panel">
          <div class="panel-header">
            <h3>评测用例</h3>
            <span class="muted">{{ evaluationCases.length }} 条</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>问题</th>
                  <th>期望意图</th>
                  <th>期望文档</th>
                  <th>期望 Chunk</th>
                  <th>标签</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in evaluationCases" :key="item.case_id">
                  <td class="strong">{{ item.question }}</td>
                  <td>{{ item.expected_intent || '-' }}</td>
                  <td>{{ item.expected_doc_id || '-' }}</td>
                  <td>{{ item.expected_chunk_ids?.length || 0 }}</td>
                  <td>{{ item.tags?.join('、') || '-' }}</td>
                  <td><StatusPill :status="item.status" /></td>
                </tr>
                <tr v-if="!evaluationCases.length">
                  <td colspan="6" class="empty">暂无评测用例。</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <h3>最新评测结果</h3>
              <p class="muted">失败项可以回流到知识补充、分块优化、相似问扩展或发布检查。</p>
            </div>
            <button class="btn" @click="loadEvaluationRuns">刷新报告</button>
          </div>
          <div v-if="latestRun" class="eval-results">
            <article v-for="result in latestRun.results" :key="result.case_id" class="eval-result">
              <div class="eval-result-head">
                <div>
                  <strong>{{ result.question }}</strong>
                  <p>{{ result.hit_reason }} · Rank: {{ result.rank || '-' }} · TopScore: {{ result.top_score }}</p>
                </div>
                <StatusPill :status="result.passed ? 'passed' : 'failed'" />
              </div>
              <div v-if="result.hits?.length" class="recall-results">
                <article v-for="hit in result.hits.slice(0, 2)" :key="hit.chunk_id" class="recall-hit">
                  <div class="recall-hit-head">
                    <div>
                      <strong>{{ hit.document_title }}</strong>
                      <p>{{ hit.title_path || '正文片段' }} · {{ hit.metadata?.category }} · {{ statusLabel(hit.metadata?.status) }}</p>
                    </div>
                    <span class="score">{{ hit.score }}</span>
                  </div>
                  <p class="chunk-content">{{ hit.content }}</p>
                </article>
              </div>
              <div v-else class="hit-debug">没有召回结果，建议检查知识是否发布、标准问题是否需要相似问、分块是否保留关键上下文。</div>
            </article>
          </div>
          <div v-else class="empty">暂无评测结果。</div>
        </section>
      </section>

      <section v-if="activeTab === 'tickets'" class="page">
        <div class="ticket-layout">
          <section class="panel">
            <div class="panel-header">
              <h3>工单列表</h3>
              <button class="btn" @click="loadTickets">刷新</button>
            </div>
            <button
              v-for="ticket in tickets"
              :key="ticket.ticket_id"
              class="ticket-row"
              :class="{ active: selectedTicket?.ticket_id === ticket.ticket_id }"
              @click="selectedTicket = ticket"
            >
              <div class="ticket-title">
                <div>
                  <h4>{{ ticket.title }}</h4>
                  <p>{{ ticket.summary }}</p>
                </div>
                <div>
                  <StatusPill :status="ticket.status" />
                  <StatusPill :status="ticket.priority" />
                </div>
              </div>
            </button>
          </section>

          <section class="panel detail-card">
            <template v-if="selectedTicket">
              <p class="eyebrow">{{ selectedTicket.ticket_id }}</p>
              <h3>{{ selectedTicket.title }}</h3>
              <p class="muted">{{ selectedTicket.summary }}</p>
              <dl class="kv">
                <div>
                  <dt>用户</dt>
                  <dd>{{ selectedTicket.user_id }}</dd>
                </div>
                <div>
                  <dt>意图</dt>
                  <dd>{{ selectedTicket.intent }}</dd>
                </div>
                <div>
                  <dt>负责人</dt>
                  <dd>{{ selectedTicket.assignee }}</dd>
                </div>
                <div>
                  <dt>更新时间</dt>
                  <dd>{{ formatDate(selectedTicket.updated_at) }}</dd>
                </div>
              </dl>
              <pre class="code">{{ JSON.stringify(selectedTicket.ai_trace, null, 2) }}</pre>
              <label class="field" style="margin-top: 16px">
                <span>处理结论</span>
                <textarea v-model="ticketResolution" class="textarea" style="min-height: 110px" />
              </label>
              <div class="grid-form" style="margin-top: 14px">
                <button class="btn" @click="updateTicket('processing')">标记处理中</button>
                <button class="btn success" @click="updateTicket('resolved')">标记已解决</button>
              </div>
            </template>
            <div v-else class="empty">选择一条工单查看详情。</div>
          </section>
        </div>
      </section>

      <section v-if="activeTab === 'compensation'" class="page">
        <div class="comp-layout">
          <section class="panel">
            <div class="panel-header">
              <div>
                <h3>用户补偿操作</h3>
                <p class="muted">当前为 mock 提交，后续可接 MCP 业务工具。</p>
              </div>
            </div>
            <div class="panel-body stack">
              <label class="field">
                <span>用户 ID</span>
                <input v-model="compensationForm.user_id" class="input" />
              </label>
              <label class="field">
                <span>补偿类型</span>
                <select v-model="compensationForm.asset_type" class="select">
                  <option value="star_energy">星能</option>
                  <option value="echo_shell">回声贝</option>
                  <option value="vip_days">VIP 天数</option>
                </select>
              </label>
              <label class="field">
                <span>数量</span>
                <input v-model.number="compensationForm.amount" type="number" min="1" class="input" />
              </label>
              <label class="field">
                <span>关联工单</span>
                <input v-model="compensationForm.related_ticket_id" class="input" placeholder="可选" />
              </label>
              <label class="field">
                <span>原因</span>
                <textarea v-model="compensationForm.reason" class="textarea" style="min-height: 110px" />
              </label>
              <button class="btn primary" :disabled="loading.compensation" @click="submitCompensation">
                {{ loading.compensation ? '提交中' : '提交补偿' }}
              </button>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>补偿记录</h3>
              <button class="btn" @click="loadCompensations">刷新</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>记录</th>
                    <th>用户</th>
                    <th>类型</th>
                    <th>数量</th>
                    <th>状态</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="record in compensations" :key="record.record_id">
                    <td class="strong">{{ record.record_id }}</td>
                    <td>{{ record.user_id }}</td>
                    <td>{{ assetLabel(record.asset_type) }}</td>
                    <td>{{ record.amount }}</td>
                    <td><StatusPill :status="record.status" /></td>
                    <td>{{ formatDate(record.created_at) }}</td>
                  </tr>
                  <tr v-if="!compensations.length">
                    <td colspan="6" class="empty">暂无补偿记录。</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { api, uploadApi } from '../utils/api'

const navItems = [
  { key: 'kb', label: '知识库构建', title: '知识库构建平台', subtitle: '飞书采集、元数据、分块预览、发布草稿', icon: '▦' },
  { key: 'eval', label: '评测中心', title: '评测中心', subtitle: '评测集、自动化运行、指标报告、BadCase 归因', icon: '◫' },
  { key: 'tickets', label: '工单处理', title: '客服工单后台', subtitle: 'AI 转人工、处理结论、BadCase 回流入口', icon: '□' },
  { key: 'compensation', label: '补偿操作', title: '用户补偿中心', subtitle: '权益补发、星能/回声贝补偿、操作留痕', icon: '◇' },
]

const activeTab = ref('kb')
const kbTab = ref('build')
const fileInputRef = ref(null)
const currentSection = computed(() => navItems.find((item) => item.key === activeTab.value) || navItems[0])
const feishuUrl = ref('')
const tagInput = ref('飞书同步')
const draft = ref({
  title: '',
  source_url: '',
  content: '',
  metadata: {
    category: '产品功能',
    product_area: 'BOU App',
    owner: '产品运营',
    version: 'v1.0',
    status: 'draft',
    visibility: '客服Agent',
    effective_at: '',
    expire_at: '',
    update_frequency: '按需更新',
    tags: ['飞书同步'],
  },
  strategy: {
    method: 'heading',
    chunk_size: 700,
    overlap: 100,
    preserve_tables: true,
    add_parent_title: true,
  },
})
const chunks = ref([])
const chunkSummary = ref(null)
const documents = ref([])
const saveNotice = ref('')
const syncingDocId = ref('')
const tickets = ref([])
const selectedTicket = ref(null)
const ticketResolution = ref('')
const compensations = ref([])
const compensationForm = ref({
  user_id: '',
  asset_type: 'star_energy',
  amount: 100,
  reason: '',
  related_ticket_id: '',
})
const loading = ref({
  fetch: false,
  preview: false,
  save: false,
  compensation: false,
  recall: false,
  upload: false,
  evalRun: false,
})
const recallForm = ref({
  query: '聊天里出现红色感叹号是怎么回事？',
  top_k: 5,
  status_filter: 'published',
})
const recallResults = ref([])
const recallSummary = ref(null)
const recallSearched = ref(false)
const evaluationCases = ref([])
const evaluationRuns = ref([])
const latestRun = ref(null)
const expectedChunkInput = ref('')
const evalCaseForm = ref({
  question: '',
  expected_answer: '',
  expected_intent: '',
  expected_doc_id: '',
  expected_chunk_ids: [],
  evaluation_type: 'rag_recall',
  tags: [],
  status: 'active',
})
const evalRunForm = ref({
  case_ids: [],
  top_k: 5,
  status_filter: 'published',
  category: '',
})

watch(tagInput, (value) => {
  draft.value.metadata.tags = value.split(',').map((tag) => tag.trim()).filter(Boolean)
})

watch(selectedTicket, (ticket) => {
  ticketResolution.value = ticket?.resolution || ''
  if (ticket) {
    compensationForm.value.user_id = ticket.user_id
    compensationForm.value.related_ticket_id = ticket.ticket_id
  }
})

const chunkSummaryText = computed(() => {
  if (!chunkSummary.value) return '用于检查切片是否完整、是否保留上下文。'
  return `${chunkSummary.value.chunk_count} 个 chunk，平均 ${chunkSummary.value.avg_tokens} tokens，最大 ${chunkSummary.value.max_tokens} tokens`
})

async function fetchFeishu() {
  loading.value.fetch = true
  try {
    const data = await api('/kb/fetch-feishu', {
      method: 'POST',
      body: JSON.stringify({ url: feishuUrl.value.trim() }),
    })
    applyImportedDocument(data)
    await previewChunks()
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.fetch = false
  }
}

function applyImportedDocument(data) {
  draft.value.title = data.title
  draft.value.source_url = data.source_url
  draft.value.content = data.content
  draft.value.metadata = { ...draft.value.metadata, ...data.suggested_metadata }
  tagInput.value = draft.value.metadata.tags.join(',')
}

function triggerFileUpload() {
  fileInputRef.value?.click()
}

async function handleFileUpload(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  loading.value.upload = true
  try {
    const data = await uploadApi('/kb/upload-file', formData)
    applyImportedDocument(data)
    await previewChunks()
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.upload = false
  }
}

async function previewChunks() {
  loading.value.preview = true
  try {
    const data = await api('/kb/chunk-preview', {
      method: 'POST',
      body: JSON.stringify({
        title: draft.value.title,
        content: draft.value.content,
        metadata: draft.value.metadata,
        strategy: draft.value.strategy,
      }),
    })
    chunks.value = data.chunks
    chunkSummary.value = data.summary
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.preview = false
  }
}

async function saveDocument() {
  loading.value.save = true
  try {
    const data = await api('/kb/documents', {
      method: 'POST',
      body: JSON.stringify({
        title: draft.value.title,
        source_url: draft.value.source_url,
        content: draft.value.content,
        metadata: draft.value.metadata,
        strategy: draft.value.strategy,
        chunks: chunks.value,
      }),
    })
    await loadDocuments()
    kbTab.value = 'documents'
    saveNotice.value = data.mode === 'updated'
      ? '已更新同来源知识文档，避免重复创建。'
      : '已保存为草稿，可在文档列表中发布。'
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.save = false
  }
}

async function loadDocuments() {
  const data = await api('/kb/documents')
  documents.value = data.documents || []
}

async function updateDocumentStatus(doc, status) {
  await api(`/kb/documents/${doc.doc_id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
  await loadDocuments()
  saveNotice.value = status === 'published' ? '文档已发布，可进入召回测试验证。' : '文档状态已更新。'
}

async function updateSyncConfig(doc, patch) {
  const current = doc.sync_config || {}
  const nextConfig = {
    sync_enabled: Boolean(current.sync_enabled),
    sync_frequency: current.sync_frequency || 'manual',
    auto_publish: Boolean(current.auto_publish),
    ...patch,
  }
  try {
    await api(`/kb/documents/${doc.doc_id}/sync-config`, {
      method: 'PATCH',
      body: JSON.stringify(nextConfig),
    })
    await loadDocuments()
    saveNotice.value = '同步配置已更新。'
  } catch (error) {
    window.alert(error.message)
    await loadDocuments()
  }
}

async function syncNow(doc) {
  syncingDocId.value = doc.doc_id
  try {
    const data = await api(`/kb/documents/${doc.doc_id}/sync-now`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
    await loadDocuments()
    saveNotice.value = data.message || '同步完成。'
  } catch (error) {
    window.alert(error.message)
  } finally {
    syncingDocId.value = ''
  }
}

async function runRecallTest() {
  loading.value.recall = true
  recallSearched.value = false
  try {
    const data = await api('/kb/recall-test', {
      method: 'POST',
      body: JSON.stringify(recallForm.value),
    })
    recallResults.value = data.results || []
    recallSummary.value = data.summary || null
    recallSearched.value = true
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.recall = false
  }
}

async function loadTickets() {
  const data = await api('/tickets')
  tickets.value = data.tickets || []
  if (!selectedTicket.value && tickets.value.length) {
    selectedTicket.value = tickets.value[0]
  }
}

async function updateTicket(status) {
  if (!selectedTicket.value) return
  const ticketId = selectedTicket.value.ticket_id
  await api(`/tickets/${ticketId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      status,
      resolution: ticketResolution.value,
    }),
  })
  await loadTickets()
  selectedTicket.value = tickets.value.find((ticket) => ticket.ticket_id === ticketId) || tickets.value[0] || null
}

async function submitCompensation() {
  loading.value.compensation = true
  try {
    await api('/compensations', {
      method: 'POST',
      body: JSON.stringify(compensationForm.value),
    })
    compensationForm.value.reason = ''
    await loadCompensations()
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.compensation = false
  }
}

async function loadCompensations() {
  const data = await api('/compensations')
  compensations.value = data.records || []
}

async function loadEvaluationCases() {
  const data = await api('/evaluations/cases')
  evaluationCases.value = data.cases || []
}

async function createEvaluationCase() {
  const payload = {
    ...evalCaseForm.value,
    expected_chunk_ids: expectedChunkInput.value.split(',').map((item) => item.trim()).filter(Boolean),
  }
  await api('/evaluations/cases', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  evalCaseForm.value = {
    question: '',
    expected_answer: '',
    expected_intent: '',
    expected_doc_id: '',
    expected_chunk_ids: [],
    evaluation_type: 'rag_recall',
    tags: [],
    status: 'active',
  }
  expectedChunkInput.value = ''
  await loadEvaluationCases()
}

async function runEvaluation() {
  loading.value.evalRun = true
  try {
    const data = await api('/evaluations/runs', {
      method: 'POST',
      body: JSON.stringify(evalRunForm.value),
    })
    latestRun.value = data
    await loadEvaluationRuns()
  } catch (error) {
    window.alert(error.message)
  } finally {
    loading.value.evalRun = false
  }
}

async function loadEvaluationRuns() {
  const data = await api('/evaluations/runs')
  evaluationRuns.value = data.runs || []
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

function assetLabel(value) {
  return {
    star_energy: '星能',
    echo_shell: '回声贝',
    vip_days: 'VIP 天数',
  }[value] || value
}

function statusLabel(value) {
  return {
    draft: '草稿',
    reviewing: '待审核',
    published: '已发布',
    archived: '已下线',
    pending: '待处理',
    processing: '处理中',
    resolved: '已解决',
    closed: '已关闭',
    mock_submitted: '已提交',
  }[value] || value || '-'
}

function recallStatusLabel(value) {
  return value === 'all' ? '全部状态' : statusLabel(value)
}

function percent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`
}

function sourceLabel(value) {
  return {
    feishu: '飞书',
    local: '本地文件',
    manual: '手动录入',
  }[value] || '未知来源'
}

function syncStatusLabel(value) {
  return {
    saved: '已保存',
    no_change: '无变化',
    changed_waiting_review: '有变更，待审核',
    changed_auto_published: '有变更，已自动发布',
  }[value] || '未同步'
}

const StatusPill = defineComponent({
  props: { status: { type: String, default: '' } },
  setup(props) {
    const labelMap = {
      draft: '草稿',
      reviewing: '待审核',
      published: '已发布',
      archived: '已下线',
      pending: '待处理',
      processing: '处理中',
      resolved: '已解决',
      closed: '已关闭',
      mock_submitted: '已提交',
      low: '低',
      medium: '中',
      high: '高',
      urgent: '紧急',
      active: '启用',
      disabled: '停用',
      passed: '通过',
      failed: '失败',
    }
    const toneMap = {
      published: 'green',
      resolved: 'green',
      mock_submitted: 'green',
      processing: 'blue',
      reviewing: 'amber',
      pending: 'amber',
      high: 'red',
      urgent: 'red',
      active: 'green',
      passed: 'green',
      failed: 'red',
    }
    return () => h('span', { class: `status ${toneMap[props.status] || ''}` }, labelMap[props.status] || props.status || '-')
  },
})

onMounted(() => {
  loadDocuments().catch(() => {})
  loadTickets().catch(() => {})
  loadCompensations().catch(() => {})
  loadEvaluationCases().catch(() => {})
  loadEvaluationRuns().catch(() => {})
})
</script>
