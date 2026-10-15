import {relations} from '../src/scene/relations.js';
let input='';for await(const chunk of process.stdin)input+=chunk;
process.stdout.write(JSON.stringify(relations(JSON.parse(input))));
