const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const source = fs.readFileSync(path.join(__dirname, '..', 'preview', 'app.js'), 'utf8')
const slice = (name, nextName) => source.slice(source.indexOf(`function ${name}(`), source.indexOf(`\nfunction ${nextName}(`))
const messages = []
const nodes = []
const sandbox = {
  document: {
    createElement(tag) {
      const node = { tag, children: [], classList: { add() {} }, appendChild(child) { this.children.push(child) }, set textContent(value) { this.text = value }, get textContent() { return this.text }, set className(value) { this.class = value } }
      nodes.push(node)
      return node
    },
  },
  chat: { appendChild(node) { this.row = node }, scrollTop: 0, scrollHeight: 0 },
  addMessage: (...args) => messages.push(args),
  window: {},
}
vm.createContext(sandbox)
const proposalOrderText = source.slice(source.indexOf('function proposalOrder('), source.indexOf('\nfunction openProposalDatePicker('))
const addMessageText = source.slice(source.indexOf('function addMessage('), source.indexOf('\nfunction setTab('))
vm.runInContext(`${slice('el', 'appendEventSources')}\n${addMessageText}\n${proposalOrderText}`, sandbox)

const row = sandbox.addMessage('assistant', 'Summary of current information: I need one detail.\nFollow-up questions: 1. Is shared housing okay?')
assert.match(row.children[0].text, /Follow-up questions:/)
assert.match(row.children[0].text, /Is shared housing okay\?/)
assert.equal(sandbox.proposalOrder({ title: 'Confirm onboarding with HR' }), 0)
assert.equal(sandbox.proposalOrder({ title: 'Review and sign rental agreement' }), 1)
assert.equal(sandbox.proposalOrder({ title: 'Move into the new home' }), 2)
assert.equal(sandbox.proposalOrder({ title: 'Verify broadband installation conditions' }), 3)
assert.equal(sandbox.proposalOrder({ title: 'Verify housing provident fund enrollment' }), 4)
console.log('English follow-up parsing and proposal ordering passed')
