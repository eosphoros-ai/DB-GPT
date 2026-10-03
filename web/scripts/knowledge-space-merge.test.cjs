const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');
const React = require('react');

// Exercise the real merged component's element tree and event handlers. Only
// service/UI boundaries and hook storage are stubbed; no backend is required.
function fixture(overrides = {}) {
  const values = {
    spaceName: 'wiki-space',
    owner: 'owner',
    description: 'Wiki knowledge',
    storage: 'VectorStore',
    dataSourceType: 'DOCUMENT',
    index_methods: ['VectorStore', 'FullText', 'KnowledgeGraph'],
    ...overrides,
  };
  const calls = [];
  const messages = [];
  const navigations = [];
  const steps = [];
  const states = [];
  const refs = [];
  let stateIndex = 0;
  let refIndex = 0;
  let appCalls = 0;
  let successes = 0;
  const form = {
    getFieldValue: name => values[name],
    setFieldValue: (name, value) => {
      values[name] = value;
    },
    resetFields: () => {},
  };
  const Form = Object.assign(() => null, {
    Item: 'Form.Item',
    useForm: () => [form],
    useWatch: name => values[name],
  });
  const antd = {
    App: {
      useApp: () => {
        appCalls++;
        return {
          message: Object.fromEntries(
            ['error', 'success', 'warning'].map(kind => [kind, text => messages.push({ kind, text })]),
          ),
        };
      },
    },
    Form,
    Button: 'Button',
    Checkbox: Object.assign(() => null, { Group: 'Checkbox.Group' }),
    Collapse: 'Collapse',
    Divider: 'Divider',
    Input: Object.assign(() => null, { TextArea: 'Input.TextArea' }),
    InputNumber: 'InputNumber',
    Radio: Object.assign(() => null, { Group: 'Radio.Group' }),
    Select: Object.assign(() => null, { Option: 'Select.Option' }),
    Spin: 'Spin',
    Switch: 'Switch',
    Upload: { Dragger: 'Upload.Dragger' },
  };
  // Importing static message would lose the App provider's theme/context.
  Object.defineProperty(antd, 'message', {
    get() {
      throw new Error('Use App.useApp message context, not static message');
    },
  });
  const responses = {
    addSpace: [null, [], { success: true }],
    getSpaceList: [null, [{ id: 42, name: values.spaceName }]],
    syncGitRepo: [null, { indexed: 3 }],
    uploadDocument: [null, 7],
    syncBatchDocument: [null, {}],
  };
  const api = Object.fromEntries(
    [
      'addSpace',
      'getSpaceList',
      'getModelList',
      'getChunkStrategies',
      'syncGitRepo',
      'uploadDocument',
      'syncBatchDocument',
    ].map(name => [name, (...args) => ({ name, args })]),
  );
  api.apiInterceptors = async request => {
    calls.push(request);
    return responses[request.name] || [null, []];
  };
  const deps = {
    '@/client/api': api,
    '@/components/knowledge/source/binding-wizard': { BindingWizard: 'BindingWizard' },
    '@ant-design/icons': {
      FileTextOutlined: 'FileTextOutlined',
      LinkOutlined: 'LinkOutlined',
      ReadOutlined: 'ReadOutlined',
    },
    antd,
    'next/router': { useRouter: () => ({ push: url => navigations.push(url) }) },
    react: {
      ...React,
      useState: initial => {
        const index = stateIndex++;
        if (!(index in states)) states[index] = initial;
        return [
          states[index],
          value => {
            states[index] = typeof value === 'function' ? value(states[index]) : value;
          },
        ];
      },
      useRef: initial => {
        const index = refIndex++;
        return refs[index] || (refs[index] = { current: initial });
      },
      useMemo: callback => callback(),
      useEffect: () => {},
    },
    'react-i18next': { useTranslation: () => ({ t: key => key }) },
  };
  const filename = path.join(__dirname, '../components/knowledge/space-form.tsx');
  const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('require', 'module', 'exports', 'localStorage', source)(
    name => deps[name] || require(name),
    loadedModule,
    loadedModule.exports,
    { setItem: () => {} },
  );
  const render = () => {
    stateIndex = 0;
    refIndex = 0;
    return loadedModule.exports.default({
      handleStepChange: step => steps.push(step),
      spaceConfig: [{ name: 'VectorStore' }],
      onSuccess: () => {
        successes++;
      },
    });
  };
  const submit = async fields => {
    Object.assign(values, fields);
    const root = render();
    await all(root)
      .find(node => node.type === Form)
      .props.onFinish({ ...values });
  };
  return {
    render,
    submit,
    values,
    form,
    calls,
    messages,
    navigations,
    steps,
    responses,
    get appCalls() {
      return appCalls;
    },
    get successes() {
      return successes;
    },
  };
}

function all(root) {
  if (!root || typeof root !== 'object') return [];
  if (Array.isArray(root)) return root.flatMap(all);
  return [root, ...all(root.props?.children)];
}

const fields = tree => all(tree).filter(node => node.type === 'Form.Item');

test('source-first wizard renders one index selector with Wiki and a single initial-value owner', () => {
  const f = fixture();
  const tree = f.render();
  const items = fields(tree);
  const indices = items.filter(item => item.props.name === 'index_methods');
  assert.equal(indices.length, 1);
  assert.ok(items.findIndex(item => item.props.name === 'dataSourceType') < items.indexOf(indices[0]));
  assert.equal(indices[0].props.initialValue, undefined);
  const form = all(tree).find(node => node.props?.name === 'create_knowledge');
  assert.deepEqual(form.props.initialValues.index_methods, ['VectorStore', 'FullText', 'KnowledgeGraph']);
  assert.ok(all(indices[0]).some(node => node.props?.value === 'Wiki'));
  assert.equal(f.appCalls, 1);
  assert.equal(
    items.some(item => item.props.name === 'wiki_model'),
    false,
  );
  f.values.index_methods = ['VectorStore', 'Wiki'];
  const wikiFields = fields(f.render()).map(item => item.props.name);
  for (const name of ['wiki_granularity', 'wiki_model', 'wiki_max_pages', 'wiki_content_instructions']) {
    assert.ok(wikiFields.includes(name), name);
  }
});

test('Wiki configuration is submitted intact, with defaults and no stale config when disabled', async () => {
  for (const options of [
    { index_methods: ['Wiki'], expected: { granularity: 'standard' } },
    {
      index_methods: ['VectorStore', 'Wiki'],
      wiki_granularity: 'exhaustive',
      wiki_model: 'model-a',
      wiki_max_pages: 12,
      wiki_content_instructions: 'Keep source links',
      expected: {
        granularity: 'exhaustive',
        synthesis_model: 'model-a',
        max_pages_per_ingest: 12,
        content_instructions: 'Keep source links',
      },
    },
    { index_methods: ['FullText'], wiki_model: 'stale-model', expected: undefined },
  ]) {
    const { expected, ...input } = options;
    const f = fixture();
    await f.submit({ ...input, dataSourceType: 'TEXT' });
    const payload = f.calls.find(call => call.name === 'addSpace').args[0];
    assert.deepEqual(payload.context?.wiki_config, expected);
    assert.equal(payload.vector_type, input.index_methods[0]);
    assert.equal(payload.domain_type, 'Normal');
    assert.deepEqual(f.steps, [{ label: 'forward', spaceName: 'wiki-space', pace: 2, docType: 'TEXT', files: [] }]);
  }
});

for (const [source, connector] of [
  ['FEISHU_WIKI', 'feishu_wiki'],
  ['YUQUE', 'yuque'],
  ['RSS', 'rss'],
]) {
  for (const finish of ['onCreated', 'onClose']) {
    test(`${source} keeps its embedded connector flow and ${finish} returns to the detail page`, async () => {
      const f = fixture();
      await f.submit({ dataSourceType: source, index_methods: ['VectorStore', 'Wiki'] });
      const binding = all(f.render()).find(node => node.type === 'BindingWizard');
      assert.ok(binding);
      assert.equal(binding.props.initialType, connector);
      assert.equal(binding.props.spaceId, 42);
      assert.equal(binding.props.embedded, true);
      binding.props[finish]();
      assert.equal(f.successes, 1);
      assert.deepEqual(f.steps, [{ label: 'finish' }]);
      assert.deepEqual(f.navigations, ['/construct/knowledge/detail?spaceName=wiki-space']);
      assert.equal(f.messages.at(-1).kind, 'success');
    });
  }
}

test('failed space creation uses App message context and never advances to binding', async () => {
  const f = fixture();
  f.responses.addSpace = [new Error('create failed'), undefined, { success: false }];
  await f.submit({ dataSourceType: 'YUQUE', index_methods: ['Wiki'] });
  assert.equal(f.messages.at(-1).kind, 'error');
  assert.equal(f.calls.length, 1);
  assert.equal(
    all(f.render()).some(node => node.type === 'BindingWizard'),
    false,
  );
  assert.deepEqual(f.steps, []);
});

test('missing created-space lookup finishes safely with an App-context warning', async () => {
  const f = fixture();
  f.responses.getSpaceList = [null, []];
  await f.submit({ dataSourceType: 'RSS', index_methods: ['Wiki'] });
  assert.deepEqual(f.messages, [{ kind: 'warning', text: 'ks_created_go_bind' }]);
  assert.deepEqual(f.steps, [{ label: 'finish' }]);
  assert.equal(f.successes, 1);
  assert.equal(
    all(f.render()).some(node => node.type === 'BindingWizard'),
    false,
  );
});

test('Git source still syncs before navigating and carries Wiki configuration', async () => {
  const f = fixture();
  await f.submit({
    dataSourceType: 'GIT_REPO',
    repo_url: 'https://example.test/wiki.git',
    index_methods: ['VectorStore', 'Wiki'],
  });
  const payload = f.calls.find(call => call.name === 'addSpace').args[0];
  assert.equal(payload.domain_type, 'GitRepo');
  assert.deepEqual(payload.context.wiki_config, { granularity: 'standard' });
  const sync = f.calls.find(call => call.name === 'syncGitRepo');
  assert.equal(sync.args[1].branch, 'main');
  assert.deepEqual(f.steps, [{ label: 'finish' }]);
  assert.equal(f.messages.at(-1).kind, 'success');
  assert.deepEqual(f.navigations, ['/construct/knowledge/detail?spaceName=wiki-space']);
});
