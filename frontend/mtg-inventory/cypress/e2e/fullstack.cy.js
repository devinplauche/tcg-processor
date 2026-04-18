describe("Full-stack smoke", () => {
  it("serves frontend and backend health", () => {
    cy.request("/").then((response) => {
      expect(response.status).to.eq(200);
      expect(response.body).to.be.a("string");
      expect(response.body.length).to.be.greaterThan(0);
    });

    cy.request("http://localhost:8080/api/v1/health").then((response) => {
      expect(response.status).to.eq(200);
      expect(response.body.status).to.eq("UP");
      expect(response.body.service).to.eq("mtg-api-gateway");
    });
  });
});
