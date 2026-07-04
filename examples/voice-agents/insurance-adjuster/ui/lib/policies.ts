export type PolicyEndorsement = {
  code: string;
  label: string;
  limit?: string;
};

export type PolicyData = {
  policyNumber: string;
  state: string;
  stateCode: string;
  policyType: string;
  insurer: string;
  address: string;
  city: string;
  yearBuilt: number;
  construction: string;
  roofYear: number;
  sqft: number;
  coverageA: number;
  coverageB: number;
  coverageC: string;
  coverageCLimit: number;
  coverageD: number;
  coverageE: number;
  coverageF: number;
  standardDeductible: number;
  specialDeductible: string | null;
  specialDeductibleLabel: string | null;
  specialDeductibleAmount: number | null;
  endorsements: PolicyEndorsement[];
  priorClaimsCount: number;
  floodNote: string | null;
};

export const POLICIES: Record<string, PolicyData> = {
  'FL-HO3-001': {
    policyNumber: 'FL-HO3-001',
    state: 'Florida',
    stateCode: 'FL',
    policyType: 'HO-3 Special Form',
    insurer: 'Coastal Shield Insurance',
    address: '412 Pelican Drive',
    city: 'Cape Coral, FL 33914',
    yearBuilt: 2004,
    construction: 'Concrete Block Stucco',
    roofYear: 2019,
    sqft: 2340,
    coverageA: 485000,
    coverageB: 48500,
    coverageC: 'ACV',
    coverageCLimit: 242500,
    coverageD: 97000,
    coverageE: 300000,
    coverageF: 5000,
    standardDeductible: 2500,
    specialDeductible: 'hurricane',
    specialDeductibleLabel: 'Hurricane (2% of Cov A)',
    specialDeductibleAmount: 9700,
    endorsements: [
      { code: 'HO 04 95', label: 'Water Backup & Sump', limit: '$10,000' },
      { code: 'HO 04 77', label: 'Ordinance or Law', limit: '25% of Cov A' },
      { code: 'HO 04 46', label: 'Inflation Guard', limit: '6% annual' },
    ],
    priorClaimsCount: 2,
    floodNote: 'Separate NFIP policy NF-8842271 in force. Zone AE.',
  },
  'CA-HO3-002': {
    policyNumber: 'CA-HO3-002',
    state: 'California',
    stateCode: 'CA',
    policyType: 'HO-3 (California Edition)',
    insurer: 'Pacific Crest Mutual',
    address: '2891 Hillcrest Court',
    city: 'Pasadena, CA 91107',
    yearBuilt: 1962,
    construction: 'Wood Frame / Stucco',
    roofYear: 2018,
    sqft: 2050,
    coverageA: 620000,
    coverageB: 62000,
    coverageC: 'ACV',
    coverageCLimit: 310000,
    coverageD: 186000,
    coverageE: 500000,
    coverageF: 5000,
    standardDeductible: 1500,
    specialDeductible: null,
    specialDeductibleLabel: null,
    specialDeductibleAmount: null,
    endorsements: [
      { code: 'HO 04 61', label: 'Scheduled Property', limit: '$28,800 (3 items)' },
      { code: 'HO 04 77', label: 'Ordinance or Law', limit: '50% of Cov A' },
      { code: 'HO 04 95', label: 'Water Backup & Sump', limit: '$15,000' },
      { code: 'HO 04 46', label: 'Inflation Guard', limit: '7% annual' },
    ],
    priorClaimsCount: 1,
    floodNote: null,
  },
  'TX-HO3-003': {
    policyNumber: 'TX-HO3-003',
    state: 'Texas',
    stateCode: 'TX',
    policyType: 'HO-B (Texas Form)',
    insurer: 'Lone Star Home Assurance',
    address: '5508 Sycamore Bend Lane',
    city: 'Katy, TX 77494',
    yearBuilt: 2011,
    construction: 'Brick Veneer / Wood Frame',
    roofYear: 2011,
    sqft: 3150,
    coverageA: 540000,
    coverageB: 54000,
    coverageC: 'RC',
    coverageCLimit: 270000,
    coverageD: 108000,
    coverageE: 300000,
    coverageF: 5000,
    standardDeductible: 5000,
    specialDeductible: 'wind/hail',
    specialDeductibleLabel: 'Wind & Hail (1% of Cov A)',
    specialDeductibleAmount: 5400,
    endorsements: [
      { code: 'HO 04 90', label: 'Personal Property RC', limit: 'Full RC basis' },
      { code: 'HO 04 95', label: 'Water Backup & Sump', limit: '$10,000' },
      { code: 'Cosmetic Excl', label: 'Cosmetic Damage Excl.', limit: 'Roof only' },
    ],
    priorClaimsCount: 2,
    floodNote: null,
  },
};
