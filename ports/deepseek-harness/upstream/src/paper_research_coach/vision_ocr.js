ObjC.import('Vision');
function run(args) {
    const url = $.NSURL.fileURLWithPath(args[0]);
    const request = $.VNRecognizeTextRequest.alloc.init;
    request.recognitionLevel = 0;
    request.recognitionLanguages = $(['zh-Hans', 'zh-Hant', 'en-US']);
    const handler = $.VNImageRequestHandler.alloc.initWithURLOptions(url, $({}));
    const error = Ref();
    if (!handler.performRequestsError($([request]), error)) throw Error(ObjC.unwrap(error[0].localizedDescription));
    const lines = [];
    for (let i = 0; i < request.results.count; ++i) {
        const text = request.results.objectAtIndex(i).topCandidates(1).firstObject;
        if (text) lines.push(ObjC.unwrap(text.string));
    }
    return lines.join('\n');
}
