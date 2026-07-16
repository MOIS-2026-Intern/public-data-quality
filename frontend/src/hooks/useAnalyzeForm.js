import { useState } from "react";

export function useAnalyzeForm() {
  const [sourceType, setSourceType] = useState("file");
  const [datasetFiles, setDatasetFiles] = useState([]);
  const [urlListFiles, setUrlListFiles] = useState([]);
  const [dataUrl, setDataUrl] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [apiServiceKey, setApiServiceKey] = useState("");
  const [apiPageNo, setApiPageNo] = useState("1");
  const [apiNumOfRows, setApiNumOfRows] = useState("100");
  const [apiResponseType, setApiResponseType] = useState("json");
  const [apiResponseTypeParam, setApiResponseTypeParam] = useState("_type");
  const [apiParams, setApiParams] = useState("");
  const [useLlm] = useState(true);
  const [openAiApiKey, setOpenAiApiKey] = useState("");
  const [llmFastModel, setLlmFastModel] = useState("openai/gpt-5-nano");
  const [llmStrongModel, setLlmStrongModel] = useState("openai/gpt-5-mini");

  return {
    values: {
      sourceType,
      datasetFiles,
      urlListFiles,
      dataUrl,
      apiUrl,
      apiServiceKey,
      apiPageNo,
      apiNumOfRows,
      apiResponseType,
      apiResponseTypeParam,
      apiParams,
      useLlm,
      openAiApiKey,
      llmFastModel,
      llmStrongModel,
    },
    actions: {
      setSourceType,
      setDatasetFiles,
      setUrlListFiles,
      setDataUrl,
      setApiUrl,
      setApiServiceKey,
      setApiPageNo,
      setApiNumOfRows,
      setApiResponseType,
      setApiResponseTypeParam,
      setApiParams,
      setOpenAiApiKey,
      setLlmFastModel,
      setLlmStrongModel,
    },
  };
}
