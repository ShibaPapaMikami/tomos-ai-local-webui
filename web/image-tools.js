(function () {
  function isImageGenerationRequest(text) {
    const normalized = text.trim();
    return (
      /^画像生成\s*[:：]/.test(normalized) ||
      /画像を?(生成|作成|つくって|作って|描いて)/.test(normalized) ||
      /(生成|作成|つくって|作って|描いて).{0,12}画像/.test(normalized) ||
      /^(draw|generate|create)\s+.*\b(image|picture|photo)\b/i.test(normalized)
    );
  }

  function extractImagePrompt(text) {
    let prompt = text.trim();
    prompt = prompt.replace(/^画像生成\s*[:：]\s*/i, "");
    prompt = prompt.replace(/^画像を?(生成|作成|つくって|作って|描いて)\s*[:：]?\s*/i, "");
    prompt = prompt.replace(/(?:の)?画像を?(生成|作成|つくって|作って|描いて)(して)?[。.!！]*$/i, "");
    prompt = prompt.replace(/^(draw|generate|create)\s+/i, "");
    prompt = prompt.replace(/\b(image|picture|photo)\b/gi, "");
    return prompt.replace(/\s+/g, " ").trim() || text.trim();
  }

  function parseImageOptions(text) {
    const size = text.match(/(\d{2,4})\s*[x×]\s*(\d{2,4})/i);
    const steps = text.match(/steps?\s*[:=]\s*(\d+)/i) || text.match(/ステップ\s*[:=]?\s*(\d+)/);
    const seed = text.match(/seed\s*[:=]\s*(-?\d+)/i) || text.match(/シード\s*[:=]?\s*(-?\d+)/);
    return {
      width: size ? size[1] : 512,
      height: size ? size[2] : 512,
      steps: steps ? steps[1] : 8,
      cfg: 7,
      seed: seed ? seed[1] : -1,
    };
  }

  window.GEMMA_IMAGE_TOOLS = {
    isImageGenerationRequest,
    extractImagePrompt,
    parseImageOptions,
  };
})();
