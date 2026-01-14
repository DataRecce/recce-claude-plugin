export declare class RecceDocsServer {
    private server;
    private cache;
    private searchIndex;
    private isReady;
    constructor();
    private registerTools;
    private ensureReady;
    private loadFromCache;
    private syncDocs;
    private getNextCheckDate;
    private buildSectionTree;
    run(): Promise<void>;
}
