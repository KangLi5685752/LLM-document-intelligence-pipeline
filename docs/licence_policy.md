# Portfolio Corpus Licence Policy

## Purpose and disclaimer

This is a portfolio data-governance policy, not legal advice. It defines conservative repository rules for reviewing candidate sources. Each source must be assessed individually against its own copyright notice, licence statement, contents, and intended use. Publication on GOV.UK or another public-sector website does not by itself confirm that every part of a document may be redistributed.

Authoritative reference points include the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) and [The National Archives guidance on the OGL](https://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/uk-government-licensing-framework/open-government-licence/).

## Open Government Licence requirements

Where information is expressly made available under the Open Government Licence (OGL), reuse must acknowledge the information source by including or linking to any attribution specified by the information provider and, where possible, linking to the applicable licence. If no specific statement is supplied, the OGL provides a standard public-sector-information attribution. The project must record the applicable version and exact attribution rather than assuming one from the publisher or domain.

OGL coverage is not universal:

- Third-party material is not automatically covered when the information provider is not authorised to license it.
- Personal data is not covered by the OGL and requires a separate data-protection assessment.
- Departmental or public-sector logos, crests, the Royal Arms, trade marks, and other intellectual-property rights may fall outside the licence.
- Photographs and externally copyrighted charts, illustrations, or other graphics require separate rights review.
- A document-level OGL notice may include an “except where otherwise stated” limitation that must be checked against the document contents.

## Default repository rule

- Public source files remain local and are not committed unless redistribution is explicitly approved for the specific file and intended repository use.
- Metadata, landing-page URLs, and verified direct-file URLs may be committed when they do not contain secrets or restricted data.
- Derived text may be committed only when the licence and data-risk review explicitly permit it.
- A permissive website-wide statement must not replace review of the downloaded file's copyright page, footnotes, image credits, appendices, and embedded third-party material.
- Until review is complete, the source remains candidate or deferred and its redistribution decision remains licence_review_required or metadata_only.

## Required attribution record

For every approved use, record:

- source ID, title, information provider, publisher, and copyright owner when identified;
- publication date or version and the landing-page and direct-file URLs;
- licence name and version;
- the exact attribution statement required by the provider, or the approved default statement when applicable;
- the location of licence evidence in the file or on an authoritative page and the date checked;
- any exclusions, third-party credits, logo, photograph, graphic, or personal-data findings;
- the reviewer, review date, intended use, redistribution decision, and derived-text decision.

## Licence-decision values

- **approved_local_only:** local project use is approved, but the original file must not be committed or redistributed.
- **approved_for_redistribution:** repository redistribution is explicitly supported by recorded evidence and attribution requirements.
- **metadata_only:** only metadata and source links may be retained in the repository.
- **licence_review_required:** no use or redistribution conclusion has been reached; further review is required.
- **rejected:** the source is unsuitable for the intended use because the rights or data risks cannot be resolved within project scope.

## Per-document review checklist

- [ ] Confirm the landing page, publisher, title, version, publication date, and direct-file URL.
- [ ] Inspect the file's copyright and licence notice; do not rely only on the website footer.
- [ ] Record the licence name, version, evidence location, and any required attribution exactly.
- [ ] Identify the copyright owner and whether the publisher has authority to license the material.
- [ ] Review third-party quotations, datasets, charts, photographs, illustrations, appendices, and commissioned content.
- [ ] Review logos, crests, trade marks, and externally copyrighted graphics separately.
- [ ] Assess whether personal data is present and whether it is necessary for the planned use.
- [ ] Decide whether the original file may remain local, be redistributed, or be represented by metadata only.
- [ ] Decide separately whether derived text may be stored or committed.
- [ ] Record the corpus status, reviewer, review date, decision rationale, and any unresolved conditions.
- [ ] Recheck the source when a new version appears or a document is withdrawn or superseded.
