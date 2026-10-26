/** Every Finnish text of the UI. Components take their texts from here. */
export const fi = {
  app: {
    title: "Kuittisovellus",
    navigation: "Päävalikko",
  },
  backendUnreachable: "Taustapalveluun ei saada yhteyttä.",
  status: {
    label: "Palveluiden tila",
    allOk: "Kaikki palvelut toiminnassa",
    ollamaUnreachable: "Ollamaan ei saada yhteyttä. Käynnistä Ollama.",
    modelMissing: (model: string) =>
      `Mallia ${model} ei ole ladattu. Lataa se komennolla: ollama pull ${model}`,
    ocrUnavailable: "Tekstintunnistus ei ole käytettävissä.",
    foldersUnavailable: "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
    databaseUnavailable: "Tietokanta ei ole käytettävissä.",
  },
} as const;
