#!/usr/bin/env node
// src/index.ts
import { RecceDocsServer } from './server.js';

const server = new RecceDocsServer();
server.run().catch(console.error);
